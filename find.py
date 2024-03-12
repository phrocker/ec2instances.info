import boto3
import json
from concurrent import futures
from concurrent.futures import ThreadPoolExecutor

def get_prices_in_parallel(instance_types, region = 'us-east-1'):
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_instance = {executor.submit(get_on_demand_hourly_price, instance, region): instance for instance in instance_types}
        results = []
        for future in futures.as_completed(future_to_instance):
            instance = future_to_instance[future]
            try:
                price = future.result()
                if float(price) > 0:
                    results.append({"sku": instance, "hourly_price": float(price)})
            except Exception as exc:
                print(f'{instance} generated an exception: {exc}')
        return results

# Replace the sequential part with:
#hourly_prices = get_prices_in_parallel(matching_instances)

# Initialize Boto3 clients
ec2_client = boto3.client('ec2', region_name='us-east-1')
pricing_client = boto3.client('pricing', region_name='us-east-1')

def get_matching_instances(desired_cpus, desired_memory_gb, requires_nvme):
    # Fetch all instance types (note: consider implementing pagination for production use)
    paginator = ec2_client.get_paginator('describe_instance_types')
    page_iterator = paginator.paginate(PaginationConfig={'MaxItems': 1000})

    matching_instances = []

    for page in page_iterator:
        for instance in page['InstanceTypes']:
            # Check CPU and memory
            cpus = instance['VCpuInfo']['DefaultVCpus']
            memory_gb = instance['MemoryInfo']['SizeInMiB'] / 1024
            if cpus >= desired_cpus and memory_gb >= desired_memory_gb:
                # Check NVMe requirement
                ebs_info = instance.get('EbsInfo', {})
                nvme_support = ebs_info.get('NvmeSupport', None)
                
                if requires_nvme and nvme_support == 'required':
                    matching_instances.append(instance['InstanceType'])
                elif not requires_nvme:
                    matching_instances.append(instance['InstanceType'])

    return matching_instances

def get_on_demand_hourly_price(instance_type, region):
    # Convert region name to location to use in pricing API
    region_to_location = {
        'us-east-1': 'US East (N. Virginia)',
        # Add other regions as needed
    }
    location = region_to_location.get(region, region)
    
    price_filters = [
        {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
        {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
        {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
        {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'shared'},
        {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'},
        {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used'},
    ]
    
    response = pricing_client.get_products(ServiceCode='AmazonEC2', Filters=price_filters)
    price_list = response['PriceList']
    if price_list and len(price_list) > 0:
        od = json.loads(price_list[0])['terms']['OnDemand']
        id1 = list(od)[0]
        id2 = list(od[id1]['priceDimensions'])[0]
        return od[id1]['priceDimensions'][id2]['pricePerUnit']['USD']
    else:
        return -1

def get_instance_price(instance_type):
    # Define your filters here
    filters = [
        {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
        {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': 'US East (N. Virginia)'},
        {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
        {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'},
        {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'shared'},
        {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used'},
    ]

    response = pricing_client.get_products(ServiceCode='AmazonEC2', Filters=filters, MaxResults=1)
    print(f"got {response}")
    details = json.loads(response['PriceList'][0])
    return details

# Example: Search for instances with at least 4 CPUs, 8 GiB of memory, requiring NVMe storage
matching_instances = get_matching_instances(4, 8, False)


# For demonstration, just get the price of the first matching instance
if matching_instances:
    num_instances = len(matching_instances)
    print(f"Size is {num_instances} ")
    hourly_prices = []
    hourly_prices = get_prices_in_parallel(matching_instances)
    for price_details in hourly_prices:
        print(f"Matched instance {price_details}")
        #price_details = get_on_demand_hourly_price(matched_instance, 'us-east-1')
        price = float(price_details['hourly_price'])
        if price > 0:
            hourly_prices.append( {"sku": price_details['sku'], "hourly_price": price})
    lowest_cost_instance = min(hourly_prices, key=lambda x: x["hourly_price"])
    print(f"Lowest cost {lowest_cost_instance}")
else:
    print("No matching instances found.")
