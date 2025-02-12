#!/bin/bash
curl -X POST \
  https://management.azure.com/subscriptions/$$$sub-id/providers/Microsoft.CostManagement/query?api-version=2021-10-01 \
  -H "Authorization: Bearer $$$TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "type": "Usage",
        "timeframe": "Custom",
        "timePeriod": {
          "from": "2024-11-01",
          "to": "2024-12-20"
        },
        "dataset": {
          "granularity": "Daily",
          "aggregation": {
            "totalCost": {
              "name": "PreTaxCost",
              "function": "Sum"
            }
          },
          "grouping": [
            {
              "type": "Dimension",
              "name": "ServiceName"
            }
          ]
        }
      }' > costes.txt
