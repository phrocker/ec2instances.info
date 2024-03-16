import json

def load_instance_data(file_path="www/instances.json"):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

def get_on_demand_price(instance, region='us-east-1', os_type='linux'):
    # Assume instance['pricing'] structure matcgrep boto3hes your JSON snippet
    pricing_info = instance.get('pricing', {}).get(region, {}).get(os_type, {}).get('ondemand', None)
    if pricing_info:
        return float(pricing_info)
    return None

def find_lowest_cost_instance(instances, desired_cpus, desired_memory_gb, requires_nvme, region='us-east-1', os_type='linux'):
    lowest_cost_instance = None
    lowest_price = float('inf')

    for instance in instances:
        if instance['vCPU'] >= desired_cpus and instance['memory'] >= desired_memory_gb:
            if not requires_nvme or (requires_nvme and (instance['storage'] is not None and instance['storage']['nvme_ssd'])):
                price = get_on_demand_price(instance, region, os_type)
                if price is not None and price < lowest_price:
                    lowest_cost_instance = instance
                    lowest_price = price

    return lowest_cost_instance

# Load instance data
instances = load_instance_data()

# Find the lowest cost instance
lowest_cost_instance = find_lowest_cost_instance(instances, 4, 8, True)
if lowest_cost_instance:
    print(f"Lowest cost instance: {lowest_cost_instance['instance_type']} at ${get_on_demand_price(lowest_cost_instance)} per hour")
else:
    print("No matching instances found.")