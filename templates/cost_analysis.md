# Cost Analysis Report

## {{repo.name}}
**Project Description:** 
{{repo.description}}

{% for app in applications %}

| Month | Projected Compute Cost | Projected Storage Cost
|---|---|---|
{% for costs in repo[app]['costs'] %}
|{{costs[0]}}|{{costs[1]}}|{{costs[2]}}|
{% endfor %}

### Graph of costs

![Graph of Costs]({{images[app]}} "{{app}} costs")

### Forecasting
{{forecast[app]}}

{% endfor %}


