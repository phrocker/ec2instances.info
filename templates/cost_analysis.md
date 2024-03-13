# Cost Analysis Report

## {{repo.name}}
**Project Description:** {{repo.description}}

| Month | Projected Cost |
|---|---|
{% for costs in repo.costs %}
|{{costs[0]}}|{{costs[1]}}|
{% endfor %}


### Assumptions
we need to document our assumptions here