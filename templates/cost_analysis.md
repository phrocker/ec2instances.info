# Cost Analysis Report

## Objectives of this cost analysis report

Provide cost information for the provided capabilities if they were to be moved into a cloud environment.

These will incur direct, indirect, and any opportunity costs. The direct costs will be compute, storage, and networking. For outbound data transfer, we will estimate the cost of serving the workload to consumers from a single Avaiability Zone.

This version of the estimator takes into account on-demand pricing but future versions will provide stimates for reserved instances that are not paid up front.

## {{repo.name}} cost analysis

{{repo.description}}

## Complete costs

{% for month in total_cost %}

| Month | Total Costs
|---|---|
|{{month[0]}}|{{month[1]}}
{% endfor %}


![Total Graph of Costs]({{total_cost_img}} "{{app}} Total Aggregate Costs")


## Application costs

### Forecasting
{{forecast[app]}}c

{% for app in applications %}

## Projected cost for {{app}}

| Month | Projected Compute Cost | Projected Storage Cost
|---|---|---|
{% for costs in repo[app]['costs'] %}
|{{costs[0]}}|{{costs[1]}}|{{costs[2]}}|
{% endfor %}

### Graph of costs

![Graph of Costs]({{images[app]}} "{{app}} costs")



{% endfor %}

## Assumptions
This projection assumes the applications communicating will be using private IP communications and not public Elastic IPs, which would incur fees. 

