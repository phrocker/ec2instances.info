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
            print(f"rule is {rule}")
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

class AwsPricing(Pricing):
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
            if instance['vCPU'] >= desired_cpus and instance['memory'] >= desired_memory_gb:
                if not requires_nvme or (requires_nvme and (instance['storage'] is not None and instance['storage']['nvme_ssd'])):
                    price = self._get_on_demand_price(instance, region, os_type)
                    if price is not None and price < lowest_price:
                        lowest_cost_instance = instance
                        lowest_price = price

        return { "lowest_cost_instance": lowest_cost_instance, "lowest_price": lowest_price}
    
    def find_app_def_lowest_cost_instance(self, app_def : ApplicationDefinition):
        return self.find_lowest_cost_instance(app_def.get_cpus_required(), app_def.get_memory_gb(), app_def.is_nvme_required())


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
    
    def get_daily_estimate(self, application : str , pricing : Pricing):
        app_def = self._get_application(application)
        hourly_cost = pricing.find_app_def_lowest_cost_instance( app_def )
        dep_def = self._get_deployment(application)
        print(f"hourly_cost is {hourly_cost}")
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
                return AwsPricing(self._pricing_file_path)
        raise Exception("Invalid pricing strategy")
    

    def get_begin_date(self):
        return str(self._forecast.get('begin_date',str(date.today())))




    # Load instance data


class CostAnalysis:
    def __init__(self, input_file_path : str, pricing_file_path : str):
        self._infrastructure = Infrastructure(input_file_path)
        self._forecaster = Forecaster(input_file_path, pricing_file_path)
        ## get the daily cost of the agregated infra
        self._pricing  = self._forecaster.get_pricing()

    def get_daily_pricing(self):
        app_names = self._infrastructure.get_application_names()
        total_daily_estimate = float(0.00)
        for app in app_names:
            daily_estimate = self._infrastructure.get_daily_estimate(app,self._pricing)
            # naive cost
            total_daily_estimate += daily_estimate['total_daily_cost']
        return total_daily_estimate
    
    def _calculate_monthly_costs(self, start_date_str, average_daily_cost, n_months):
        # Convert the start_date string to a datetime object
        print(start_date_str)
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        
        monthly_costs = {'Date': [], 'Cost': []}
        
        for _ in range(n_months):
            # Find the first day of the next month
            if start_date.month == 12:
                next_month = start_date.replace(year=start_date.year + 1, month=1, day=1)
            else:
                next_month = start_date.replace(month=start_date.month + 1, day=1)
            
            # Calculate the number of days in the current month
            days_in_month = (next_month - start_date).days
            
            # Calculate the cost for the current month
            monthly_cost = average_daily_cost * days_in_month
            monthly_costs['Date'].append(start_date.strftime("%Y-%m"))
            monthly_costs['Cost'].append(monthly_cost)
            #({start_date.strftime("%Y-%m"), monthly_cost))
            
            # Update the start_date to the first day of the next month
            start_date = next_month
            
        return monthly_costs


    def forecast_monthly_cost(self):
        daily_pricing = self.get_daily_pricing()
        return self._calculate_monthly_costs( self._forecaster.get_begin_date(), daily_pricing, 12)
        # using the forecaster we want to 


            

if __name__ == "__main__":
    cost_analysis = CostAnalysis('elastic.yaml', 'www/instances.json')
    daily_price = cost_analysis.get_daily_pricing()
    print(f"Total daily cost: {daily_price}")
    monthly_costs = cost_analysis.forecast_monthly_cost()
    print(f"Total monthly cost: {monthly_costs}")
    
    df = pd.DataFrame(monthly_costs)

    # Convert the 'Date' column to datetime format for better handling
    df['Date'] = pd.to_datetime(df['Date'])
    plt.figure(figsize=(10, 6))  # Set the figure size
    plt.plot(df['Date'], df['Cost'], marker='o', linestyle='-', color='b')  # Plot the data
    plt.title('Daily Costs Over Time')  # Title of the plot
    plt.xlabel('Date')  # Label for the x-axis
    plt.ylabel('Cost ($)')  # Label for the y-axis
    plt.xticks(rotation=45)  # Rotate date labels for better readability
    plt.tight_layout()  # Automatically adjust subplot parameters to give specified padding
    plt.grid(True)  # Add grid for better readability
    plt.savefig('daily_costs_over_time.png', dpi=300)  # Save the plot as a PNG file with high resolution
