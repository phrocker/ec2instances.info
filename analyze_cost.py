import argparse
import yaml

# Instantiate the parser
parser = argparse.ArgumentParser(description='Creates a database from an AWS pricing doc')

parser.add_argument('--input_file', type=str,
                    help='Input Yaml Configuration')

# Optional positional argument
parser.add_argument('--pricing_information', type=str,
                    help='Pricing information')

args = parser.parse_args()

input_file = args.input_file
pricing_information = args.pricing_information

# Read YAML file
with open(input_file, 'r') as stream:
    data_loaded = yaml.safe_load(stream)

print(data_loaded['description'])


