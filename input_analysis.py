from datetime import datetime, timedelta, date
import yaml
import json
import pandas as pd
import matplotlib.pyplot as plt
from jinja2 import Template
import codecs

class SingleInstanceCostEstimator:
    def __init__(self, price_per_instance_hour, min_deployed, max_deployed, scaling_rules):
        """
        Initializes the estimator with detailed configuration for utilization and scaling.
        :param price_per_instance_hour: Cost of running a single instance per hour.
        :param min_deployed: Minimum number of instances deployed.
        :param max_deployed: Maximum number of instances deployed.
        :param scaling_rules: Scaling rules based on CPU utilization.
        """
        self.price_per_instance_hour = price_per_instance_hour['lowest_price']
        self.min_deployed = min_deployed
        self.max_deployed = max_deployed
        self.scaling_rules = scaling_rules
        self.instances = min_deployed

    def _adjust_instances_based_on_utilization(self, cpu_utilization):
        """
        Adjusts the number of instances based on CPU utilization according to the scaling rules.
        :param cpu_utilization: Average CPU utilization (0-100).
        """
        for rule in self.scaling_rules:
            if cpu_utilization > rule['cpu_utilization_above']:
                self.instances = min(self.instances + rule['scale_up'], self.max_deployed)
            elif cpu_utilization < rule['cpu_utilization_below']:
                self.instances = max(self.instances - rule['scale_down'], self.min_deployed)

    def estimate_daily_cost(self, average_utilization, average_daily_hours, peak_usage_hours):
        """
        Estimates the cost considering the utilization hours and scaling policies.
        :param average_utilization: Average CPU utilization during active hours.
        :param average_daily_hours: Average active hours per day.
        :param peak_usage_hours: Hours of peak usage per day.
        :return: Total estimated cost for a day.
        """
        # Adjust instances for average utilization
        self._adjust_instances_based_on_utilization(average_utilization)

        # Calculate cost for average usage hours
        average_cost = self.instances * self.price_per_instance_hour * average_daily_hours

        # Assume peak usage utilizes max_deployed instances and calculate cost
        peak_cost = self.max_deployed * self.price_per_instance_hour * peak_usage_hours

        # Total daily cost
        total_daily_cost = average_cost + peak_cost

        # Provide total daily cost and base cost. We can use the base cost to compute weekend costs.
        return { "total_daily_cost" : total_daily_cost, "base_cost": average_cost }





class ApplicationDefinition:
    def __init__(self, definition):
        self._definition = definition
        if self._definition is None:
            raise Exception("Definition must be defined")

    def get_cpus_required(self) -> int:
        return self._definition.get('memory_gb', 1)
    def get_memory_gb(self) -> int:
        return self._definition.get('memory_gb', 8)
    
    def is_nvme_required(self) -> bool:
        return self._definition.get('storage', {}).get('nvme_required',False)
    
    def get_initial_storage_gb(self) -> int:
        initial_storage_str = self._definition.get('storage', {}).get('initial_storage', '0 GB')
        initial_storage_gb = int(initial_storage_str.split()[0])  # Assuming format "X GB"
        return initial_storage_gb

    def get_daily_growth_gb(self) -> int:
        daily_growth_str = self._definition.get('storage', {}).get('daily_growth', '0 GB')
        daily_growth_gb = int(daily_growth_str.split()[0])  # Assuming format "X GB"
        return daily_growth_gb

    def get_throughput_needed(self) -> int:
        throughput_needed_str = self._definition.get('storage', {}).get('throughput_needed', '0 MB/s')
        throughput_needed = int(throughput_needed_str.split()[0])  # Assuming format "X MB/s"
        return throughput_needed

class Deployment:
    def __init__(self, definition):
        self._definition = definition
        if self._definition is None:
            raise Exception("Definition must be defined")
        self.min_deployed = self._definition.get('min_deployed', 1)
        self.max_deployed = self._definition.get('max_deployed', 1)
        self.scaling_type = self._definition.get('scaling_policy', {}).get('type','static')
        default_rule = {
            'cpu_utilization_above': 1.0,
            'scale_up': 0,
            'cpu_utilization_below': 0.0,
            'scale_down': 0
        }
        default_rules = [ default_rule ]
        self.scaling_rules = self._definition.get('scaling_policy', {}).get('rules',default_rules)
        # information about utilization\
        self.average_utilization = self._definition.get('utilization', {}).get('average_utilization', float(0.80))
        self.average_daily_hours = self._definition.get('utilization', {}).get('average_daily_hours',24)
        self.peak_usage_hours = self._definition.get('utilization', {}).get('peak_usage_hours',12)



        
    
    

class Pricing:
    def get_on_demand_price(self, region : str ,  os_type : str) -> float:
        pass

    def find_lowest_cost_instance(self, desired_cpus : int, desired_memory_gb : int, requires_nvme : bool, region : str, os_type : str) -> float:
        pass

    def find_app_def_lowest_cost_instance(self, app_def : ApplicationDefinition):
        pass

class Ec2Pricing(Pricing):
    def __init__(self, file_path : str ):
        self._pricing = self._load_instance_data(file_path)

    def _load_instance_data(self, file_path="www/instances.json"):
        with open(file_path, 'r') as file:
            data = json.load(file)
        return data
    
    def _get_on_demand_price(self,instance, region='us-east-1', os_type='linux'):
        # Assume instance['pricing'] structure matches your JSON snippet
        pricing_info = instance.get('pricing', {}).get(region, {}).get(os_type, {}).get('ondemand', None)
        if pricing_info:
            return float(pricing_info)
        return None

    def find_lowest_cost_instance(self, desired_cpus, desired_memory_gb, requires_nvme, region='us-east-1', os_type='linux'):
        lowest_cost_instance = None
        lowest_price = float('inf')

        for instance in self._pricing:
            if "x86_64" not in instance.get('arch',[]):
                continue
            if instance['vCPU'] >= desired_cpus and instance['memory'] >= desired_memory_gb:
                if not requires_nvme or (requires_nvme and (instance['storage'] is not None and instance['storage']['nvme_ssd'])):
                    price = self._get_on_demand_price(instance, region, os_type)
                    if price is not None and price < lowest_price:
                        lowest_cost_instance = instance
                        lowest_price = price

        return { "lowest_cost_instance": lowest_cost_instance, "lowest_price": lowest_price}
    
    def find_app_def_lowest_cost_instance(self, app_def : ApplicationDefinition):
        return self.find_lowest_cost_instance(app_def.get_cpus_required(), app_def.get_memory_gb(), app_def.is_nvme_required())

class StoragePricingWriteout(Pricing):
    def __init__(self, file_path : str, out_file : str ):
        file_json = self._load_instance_data(file_path)
        aws_pricing_info = file_json['products']
        terms = file_json['terms']['OnDemand']
        reserved_terms = file_json['terms']['Reserved']
        storage_products = {sku: details for sku, details in aws_pricing_info.items() if details.get('productFamily') == 'Storage'}

        # Initialize a dictionary to hold the extracted data
        on_demand_pricing = {}
        reserved_pricing = {}

        for sku, product_details in storage_products.items():
            # Extract attributes and SKU
            attributes = product_details['attributes']
            
            # Step 4: Lookup the corresponding SKU for pricing info
            if sku in aws_pricing_info:
                
                pricing_info = terms[sku]
                #print(f"pricing info {pricing_info}")
                # Extracting pricing details. Assuming there's only one pricing detail per SKU for simplicity.
                # You may need to adjust this logic depending on the structure of your JSON and your specific needs.
                for offer_term, pricing_details in pricing_info.items():
                    price_dimensions = pricing_details['priceDimensions']
                    for price_dimension in price_dimensions.values():
                        description = price_dimension['description']
                        price_per_unit = price_dimension['pricePerUnit']['USD']
                        
                        # Save extracted data
                        on_demand_pricing[sku] = {
                            'attributes': attributes,
                            'description': description,
                            'price_per_unit': price_per_unit
                        }
                
        with open(out_file, 'w') as convert_file: 
            convert_file.write(json.dumps(on_demand_pricing))
    def _load_instance_data(self, file_path="www/index.json"):
        with open(file_path, 'r') as file:
            data = json.load(file)
        return data
    
def miB_to_bytes(miB):
        """Convert Mebibytes per second (MiB/s) to bytes per second."""
        return miB * 1024**2

def mB_to_bytes(mB):
    """Convert Megabytes per second (MB/s) to bytes per second."""
    return mB * 1000**2

class EbsPricing(Pricing):
    def __init__(self, file_path : str):
        self._pricing = self._load_instance_data(file_path)
        
    
    def _load_instance_data(self, file_path="www/index.json"):
        with open(file_path, 'r') as file:
            data = json.load(file)
        return data
    
    def find_lowest_cost_volume(self,throughput_needed : str):
        lowest_cost = float('inf')
        lowest_cost_volume_api_name = None

        throughputNeeded_value = int(throughput_needed.split()[0])  # Converts "500 MB/s" to 500
        throughputNeeded_bytes = mB_to_bytes(throughputNeeded_value)

        for sku, details in self._pricing.items():
            price_per_unit = float(details.get("price_per_unit", 0))
            max_volume_througput = details.get("attributes", {}).get("maxThroughputvolume", "0 MiB/s")
            maxThroughputVolume_value = int(max_volume_througput.split()[0])  # Converts "4000 MiB/s" to 4000
            volume_api_name = details.get("attributes", {}).get("volumeApiName", "")
            maxThroughputVolume_bytes = miB_to_bytes(maxThroughputVolume_value)
            
            if maxThroughputVolume_bytes >= throughputNeeded_bytes and price_per_unit < lowest_cost:
                lowest_cost = price_per_unit
                lowest_cost_volume_api_name = volume_api_name

        return lowest_cost_volume_api_name, lowest_cost


    def get_ebs_price_per_gb_month(self, volume_type : str):
        # Example pricing data, replace with actual lookup logic
        for sku, details in self._pricing.items():
            volume_api_name = details.get("attributes", {}).get("volumeApiName", "") 
            if volume_type == volume_api_name:
                return float(details.get("price_per_unit", 0))
        return 0

class Infrastructure:
    def __init__(self, input_file : str ):
        """Initialize class."""
        with open(input_file, 'r') as stream:
            self._data_loaded = yaml.safe_load(stream)
        
    def get_application_names(self):
        if self._data_loaded['infrastructure'] is not None:
            return self._data_loaded['infrastructure'].keys()
        else:
            return dict()
    
    def _get_deployment(self, name : str):
        return Deployment( self._data_loaded['infrastructure'].get(name, {}) )

    def _get_application(self, name : str):
        definition = self._data_loaded['applications'][name]
        if definition is None:
            raise Exception(f"{name} is not defined")
        return ApplicationDefinition(definition )
    
    def get_best_fit_sku(self, application, pricing: Pricing):
        app_def = self._get_application(application)
        hourly_cost = pricing.find_app_def_lowest_cost_instance( app_def )
        return hourly_cost.get('lowest_cost_instance',{})
    
    def get_daily_estimate(self, application : str , pricing : Pricing):
        app_def = self._get_application(application)
        hourly_cost = pricing.find_app_def_lowest_cost_instance( app_def )
        dep_def = self._get_deployment(application)
        estimator = SingleInstanceCostEstimator(hourly_cost,dep_def.min_deployed, dep_def.max_deployed, dep_def.scaling_rules)
        return estimator.estimate_daily_cost(dep_def.average_utilization, dep_def.average_daily_hours, dep_def.peak_usage_hours)
    
class Forecaster:
    def __init__(self, input_file : str , pricing_file_path : str):
        """Initialize class."""
        with open(input_file, 'r') as stream:
            self._data_loaded = yaml.safe_load(stream)
            self._forecast = self._data_loaded['forecast_guidelines']
        self._pricing_file_path=pricing_file_path
        
    def get_pricing(self):
        if self._forecast is not None:
            if self._forecast['cloud_provider'] is not None and self._forecast['cloud_provider'].lower() == "aws":
                return Ec2Pricing(self._pricing_file_path)
        raise Exception("Invalid pricing strategy")
    

    def get_begin_date(self):
        return str(self._forecast.get('begin_date',str(date.today())))




    # Load instance data


class CostAnalysis:
    def __init__(self, input_file_path : str, pricing_file_path : str, ebs_pricing_path : str):
        self._infrastructure = Infrastructure(input_file_path)
        self._forecaster = Forecaster(input_file_path, pricing_file_path)
        self._ebs_pricing = EbsPricing(ebs_pricing_path)
        ## get the daily cost of the agregated infra
        self._pricing  = self._forecaster.get_pricing()
        with open(input_file_path, 'r') as stream:
            self._data_loaded = yaml.safe_load(stream)
            self.project_name = self._data_loaded['name']
            self.project_description = self._data_loaded['description']

    def get_daily_pricing(self):
        app_names = self._infrastructure.get_application_names()
        total_daily_estimate = float(0.00)
        daily_pricing = {}
        for app in app_names:
            daily_estimate = self._infrastructure.get_daily_estimate(app,self._pricing)
            # naive cost
            daily_pricing[app] = daily_estimate['total_daily_cost']
        return daily_pricing
    
    def _calculate_app_monthly_costs(self, application : str, start_date_str, daily_pricing, n_months):
        # Convert the start_date string to a datetime object
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        

        storage_needs = self.forecast_storage_needs(application)

        throughput = self._data_loaded.get('applications',{}).get(application, {}).get('storage',{}).get('throughput_needed', "10 MB/s")

        volume_type = self._ebs_pricing.find_lowest_cost_volume(throughput)

        
        price_per_gb_month = volume_type[1]

        monthly_costs = {'Date': [], 'ComputeCost': [], 'StorageCost': [], 'TotalCost' :  []}
        
        for month in range(n_months):
            # Find the first day of the next month
            if start_date.month == 12:
                next_month = start_date.replace(year=start_date.year + 1, month=1, day=1)
            else:
                next_month = start_date.replace(month=start_date.month + 1, day=1)
            
            # Calculate the number of days in the current month
            days_in_month = (next_month - start_date).days
            
            # Calculate the cost for the current month
            monthly_cost = daily_pricing[application] * days_in_month
            monthly_costs['Date'].append(start_date.strftime("%Y-%m"))
            monthly_costs['ComputeCost'].append(monthly_cost)
            
            month_index_start = month * 30  # Approximate start day of the month
            month_index_end = min((month + 1) * 30, len(storage_needs))  # Approximate end day of the month
            average_storage_need = sum(storage_needs[month_index_start:month_index_end]) / days_in_month
            
            # Calculate storage cost for the month
            monthly_storage_cost = average_storage_need * price_per_gb_month
            
            monthly_costs['StorageCost'].append(monthly_storage_cost)
            monthly_costs['TotalCost'].append(monthly_storage_cost+ monthly_cost)
            #({start_date.strftime("%Y-%m"), monthly_cost))
            
            # Update the start_date to the first day of the next month
            start_date = next_month

        ## estimate storage costs
         
        return monthly_costs

    def _calculate_monthly_costs(self, start_date_str, app_daily_pricing, n_months):
        
        applications = app_daily_pricing.keys()
        
        # Convert the start_d
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        monthly_costs = {}
        for application in applications:
            monthly_costs[application] = self._calculate_app_monthly_costs(application, start_date_str, app_daily_pricing, n_months)
        
         
        return monthly_costs

    def forecast_storage_needs(self, application: str) -> list:
        app_def = self._infrastructure._get_application(application)
        initial_storage = app_def.get_initial_storage_gb()
        daily_growth = app_def.get_daily_growth_gb()
        storage_needs_over_time = [initial_storage]

        for day in range(1, 365):  # Forecasting for 365 days
            new_storage = storage_needs_over_time[-1] + daily_growth
            storage_needs_over_time.append(new_storage)

        return storage_needs_over_time

    def forecast_monthly_storage_costs(self, application: str, volume_type: str) -> dict:
        storage_needs = self.forecast_storage_needs(application)
        
        # Placeholder for the EBS price per GB-month, adjust based on your EBS volume type
        print(f"volume type is {volume_type}")
        price_per_gb_month = self._pricing.get_ebs_price_per_gb_month(volume_type)
        
        monthly_costs = {'Date': [], 'StorageCost': []}
        
        start_date = datetime.strptime(self._forecaster.get_begin_date(), "%Y-%m-%d")
        print()
        for month in range(12):  # Assuming a 12-month forecast
            if start_date.month == 12:
                next_month = start_date.replace(year=start_date.year + 1, month=1, day=1)
            else:
                next_month = start_date.replace(month=start_date.month + 1, day=1)
            
            days_in_month = (next_month - start_date).days
            month_index_start = month * 30  # Approximate start day of the month
            month_index_end = min((month + 1) * 30, len(storage_needs))  # Approximate end day of the month
            
            # Calculate average storage need for the month
            average_storage_need = sum(storage_needs[month_index_start:month_index_end]) / days_in_month
            
            # Calculate storage cost for the month
            monthly_storage_cost = average_storage_need * price_per_gb_month
            
            monthly_costs['Date'].append(start_date.strftime("%Y-%m"))
            monthly_costs['StorageCost'].append(monthly_storage_cost)
            
            
            start_date = next_month
        
        exit(1)
        return monthly_costs

    def forecast_monthly_cost(self):
        daily_pricing = self.get_daily_pricing()
        forecast = self._calculate_monthly_costs( self._forecaster.get_begin_date(), daily_pricing, 12)        
        for app in forecast.keys():
            vcpu = self._data_loaded['applications'].get(app,{}).get('cpus_required',-1)
            vmem = self._data_loaded['applications'].get(app,{}).get('memory_gb',-1)
            storage_costs = float("{:.2f}".format(sum( forecast[app]['StorageCost'])))
            sku = self._infrastructure.get_best_fit_sku(app,self._pricing).get('instance_type',{})
            forecast[app]['Details'] = f"""This Forecast was generated by searching for SKUs which met the criteria for {app}.
{app} requested {vcpu} vCPU and {vmem} GB Memory. The lowest cost sku to also meet the storage requirements was {sku}.
Based on the applications storage needs and throughput requirements the projected storage costs were {storage_costs}
for the 12 month period. 
            """
        return forecast
        # using the forecaster we want to 


            

if __name__ == "__main__":
    #storage = StoragePricingWriteout("www/index.json", "www/ebs.json")
    cost_analysis = CostAnalysis('elastic.yaml', 'www/instances.json', 'www/ebs.json')
    daily_price = cost_analysis.get_daily_pricing()
    print(f"Total daily cost: {daily_price}")
    monthly_costs_app = cost_analysis.forecast_monthly_cost()
    
    report = {}
    report['name'] = cost_analysis.project_name
    report['description'] = cost_analysis.project_description
    report['costs'] = []
    total_cost = {}
    images={}
    forecast = {}
    dates = None
    for app in monthly_costs_app.keys():
        monthly_costs = monthly_costs_app[app]
        print(f"Total monthly cost: {monthly_costs}")
        df = pd.DataFrame(monthly_costs)
        if dates is None:
            dates = []
            for index, dt in enumerate(monthly_costs['Date']):
                dates.append(dt)
                total_cost[dt] = []
        # Convert the 'Date' column to datetime format for better handling
        df['Date'] = pd.to_datetime(df['Date'])
        plt.figure(figsize=(10, 6))  # Set the figure size
        plt.plot(df['Date'], df['TotalCost'], marker='o', linestyle='-', color='b')  # Plot the data
        plt.title('Daily Costs Over Time')  # Title of the plot
        plt.xlabel('Date')  # Label for the x-axis
        plt.ylabel('TotalCost ($)')  # Label for the y-axis
        plt.xticks(rotation=45)  # Rotate date labels for better readability
        plt.tight_layout()  # Automatically adjust subplot parameters to give specified padding
        plt.grid(True)  # Add grid for better readability
        plt.savefig(app + '_daily_costs_over_time.png', dpi=300)  # Save the plot as a PNG file with high resolution
        images[app] = app + '_daily_costs_over_time.png'
        report[app] = {}
        report[app]['costs'] = []
        forecast[app] = monthly_costs['Details']
        for index, dt in enumerate(monthly_costs['Date']):
            total_cost[dt].append( [dt, monthly_costs['TotalCost'][index]])
            report[app]['costs'].append( 
                [dt,
                 float("{:.2f}".format(monthly_costs['ComputeCost'][index])),
                 float("{:.2f}".format(monthly_costs['StorageCost'][index])) ])
    
    df = pd.DataFrame(monthly_costs)
        
        # Convert the 'Date' column to datetime format for better handling
    df['Date'] = pd.to_datetime(df['Date'])
    plt.figure(figsize=(10, 6))  # Set the figure size
    plt.plot(df['Date'], df['TotalCost'], marker='o', linestyle='-', color='b')  # Plot the data
    plt.title('Daily Costs Over Time')  # Title of the plot
    plt.xlabel('Date')  # Label for the x-axis
    plt.ylabel('TotalCost ($)')  # Label for the y-axis
    plt.xticks(rotation=45)  # Rotate date labels for better readability
    plt.tight_layout()  # Automatically adjust subplot parameters to give specified padding
    plt.grid(True)  # Add grid for better readability
    plt.savefig('total_cost_img.png', dpi=300)  # Save the plot as a PNG file with high resolution
    total_cost_img = 'total_cost_img.png'


    #render the template
    with open('./templates/cost_analysis.md', 'r') as file:
        template = Template(file.read(),trim_blocks=True)
    rendered_file = template.render(repo=report, applications = monthly_costs_app.keys(), monthly_costs=monthly_costs_app, images=images, forecast=forecast, total_cost=total_cost)

    #output the file
    output_file = codecs.open("report.md", "w", "utf-8")
    output_file.write(rendered_file)
    output_file.close()
    