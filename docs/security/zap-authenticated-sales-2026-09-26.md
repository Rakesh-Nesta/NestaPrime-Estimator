# ZAP Scanning Report

ZAP by [Checkmarx](https://checkmarx.com/).


## Summary of Alerts

| Risk Level | Number of Alerts |
| --- | --- |
| High | 0 |
| Medium | 0 |
| Low | 2 |
| Informational | 3 |




## Insights

| Level | Reason | Site | Description | Statistic |
| --- | --- | --- | --- | --- |
| Low | Warning |  | ZAP warnings logged - see the zap.log file for details | 270    |
| Low | Exceeded High | http://host.docker.internal:8001 | Percentage of responses with status code 4xx | 98 % |
| Info | Informational | http://host.docker.internal:8001 | Percentage of responses with status code 2xx | 1 % |
| Info | Informational | http://host.docker.internal:8001 | Percentage of endpoints with content type application/json | 99 % |
| Info | Informational | http://host.docker.internal:8001 | Percentage of endpoints with content type image/png | 1 % |
| Info | Informational | http://host.docker.internal:8001 | Percentage of endpoints with method DELETE | 2 % |
| Info | Informational | http://host.docker.internal:8001 | Percentage of endpoints with method GET | 53 % |
| Info | Informational | http://host.docker.internal:8001 | Percentage of endpoints with method PATCH | 11 % |
| Info | Informational | http://host.docker.internal:8001 | Percentage of endpoints with method POST | 30 % |
| Info | Informational | http://host.docker.internal:8001 | Percentage of endpoints with method PUT | 2 % |
| Info | Informational | http://host.docker.internal:8001 | Count of total endpoints | 689    |
| Info | Exceeded Low | http://host.docker.internal:8001 | Percentage of slow responses | 14 % |







## Alerts

| Name | Risk Level | Number of Instances |
| --- | --- | --- |
| A Server Error response code was returned by the server | Low | 2 |
| Unexpected Content-Type was returned | Low | 2 |
| A Client Error response code was returned by the server | Informational | 676 |
| Authentication Request Identified | Informational | 2 |
| Non-Storable Content | Informational | Systemic |




## Alert Detail



### [ A Server Error response code was returned by the server ](https://www.zaproxy.org/docs/alerts/100000/)



##### Low (High)

### Description

A response code of 503 was returned by the server.
This may indicate that the application is failing to handle unexpected input correctly.
Raised by the 'Alert on HTTP Response Code Error' script

* URL: http://host.docker.internal:8001/education/ask
  * Node Name: `http://host.docker.internal:8001/education/ask ()({question,context,history:[{role,content}]})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `503`
  * Other Info: ``
* URL: http://host.docker.internal:8001/education/ask/
  * Node Name: `http://host.docker.internal:8001/education/ask/ ()({question,context,history:[{role,content}]})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `503`
  * Other Info: ``


Instances: 2

### Solution



### Reference



#### CWE Id: [ 388 ](https://cwe.mitre.org/data/definitions/388.html)


#### WASC Id: 20

#### Source ID: 4

### [ Unexpected Content-Type was returned ](https://www.zaproxy.org/docs/alerts/100001/)



##### Low (High)

### Description

A Content-Type of image/png was returned by the server.
This is not one of the types expected to be returned by an API.
Raised by the 'Alert on Unexpected Content Types' script

* URL: http://host.docker.internal:8001/company/logo
  * Node Name: `http://host.docker.internal:8001/company/logo`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `image/png`
  * Other Info: ``
* URL: http://host.docker.internal:8001/company/logo/
  * Node Name: `http://host.docker.internal:8001/company/logo/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `image/png`
  * Other Info: ``


Instances: 2

### Solution



### Reference




#### Source ID: 4

### [ A Client Error response code was returned by the server ](https://www.zaproxy.org/docs/alerts/100000/)



##### Informational (High)

### Description

A response code of 422 was returned by the server.
This may indicate that the application is failing to handle unexpected input correctly.
Raised by the 'Alert on HTTP Response Code Error' script

* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/lines/line_id
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/lines/line_id`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/lines/line_id/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/lines/line_id/`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimate-option-addons/row_id
  * Node Name: `http://host.docker.internal:8001/estimate-option-addons/row_id`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimate-option-addons/row_id/
  * Node Name: `http://host.docker.internal:8001/estimate-option-addons/row_id/`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/estimate_id/options/option_id
  * Node Name: `http://host.docker.internal:8001/estimates/estimate_id/options/option_id`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/estimate_id/options/option_id/
  * Node Name: `http://host.docker.internal:8001/estimates/estimate_id/options/option_id/`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/lighting-standards/pole-counts/sport_id
  * Node Name: `http://host.docker.internal:8001/lighting-standards/pole-counts/sport_id`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/lighting-standards/pole-counts/sport_id/
  * Node Name: `http://host.docker.internal:8001/lighting-standards/pole-counts/sport_id/`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/payment-milestones/milestone_id
  * Node Name: `http://host.docker.internal:8001/payment-milestones/milestone_id`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/payment-milestones/milestone_id/
  * Node Name: `http://host.docker.internal:8001/payment-milestones/milestone_id/`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/products/product_id
  * Node Name: `http://host.docker.internal:8001/products/product_id`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/products/product_id/
  * Node Name: `http://host.docker.internal:8001/products/product_id/`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/scope-items/selection_id
  * Node Name: `http://host.docker.internal:8001/projects/project_id/scope-items/selection_id`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/scope-items/selection_id/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/scope-items/selection_id/`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/sports/selection_id
  * Node Name: `http://host.docker.internal:8001/projects/project_id/sports/selection_id`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/sports/selection_id/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/sports/selection_id/`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/tender-details/competitor-bids/bid_id
  * Node Name: `http://host.docker.internal:8001/projects/project_id/tender-details/competitor-bids/bid_id`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/tender-details/competitor-bids/bid_id/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/tender-details/competitor-bids/bid_id/`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/sport-margin-policies/sport_id
  * Node Name: `http://host.docker.internal:8001/sport-margin-policies/sport_id`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/sport-margin-policies/sport_id/
  * Node Name: `http://host.docker.internal:8001/sport-margin-policies/sport_id/`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001
  * Node Name: `http://host.docker.internal:8001`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/
  * Node Name: `http://host.docker.internal:8001/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/6176927690798387556
  * Node Name: `http://host.docker.internal:8001/6176927690798387556`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/accessory-catalog%3Fsport_id=&include_inactive=false
  * Node Name: `http://host.docker.internal:8001/accessory-catalog (include_inactive,sport_id)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/accessory-catalog/4823912529903246831
  * Node Name: `http://host.docker.internal:8001/accessory-catalog/4823912529903246831`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/accessory-catalog/actuator/health
  * Node Name: `http://host.docker.internal:8001/accessory-catalog/actuator/health`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/attachments
  * Node Name: `http://host.docker.internal:8001/attachments`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/attachments%3Fdoc_type=cost_sheet&doc_id=doc_id&include_superseded=false
  * Node Name: `http://host.docker.internal:8001/attachments (doc_id,doc_type,include_superseded)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/attachments/
  * Node Name: `http://host.docker.internal:8001/attachments/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/attachments/4098839899857846195
  * Node Name: `http://host.docker.internal:8001/attachments/4098839899857846195`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/attachments/attachment_id
  * Node Name: `http://host.docker.internal:8001/attachments/attachment_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/attachments/attachment_id/
  * Node Name: `http://host.docker.internal:8001/attachments/attachment_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/attachments/attachment_id/7705528429210049669
  * Node Name: `http://host.docker.internal:8001/attachments/attachment_id/7705528429210049669`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/attachments/attachment_id/download
  * Node Name: `http://host.docker.internal:8001/attachments/attachment_id/download`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/attachments/attachment_id/download/
  * Node Name: `http://host.docker.internal:8001/attachments/attachment_id/download/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/audit-log
  * Node Name: `http://host.docker.internal:8001/audit-log`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/audit-log%3Fdocument_type=&document_id=
  * Node Name: `http://host.docker.internal:8001/audit-log (document_id,document_type)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/audit-log/
  * Node Name: `http://host.docker.internal:8001/audit-log/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/audit-log/5574014446233917352
  * Node Name: `http://host.docker.internal:8001/audit-log/5574014446233917352`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/audit-log/export
  * Node Name: `http://host.docker.internal:8001/audit-log/export`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/audit-log/export%3Fdocument_type=&document_id=
  * Node Name: `http://host.docker.internal:8001/audit-log/export (document_id,document_type)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/audit-log/export/
  * Node Name: `http://host.docker.internal:8001/audit-log/export/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/auth
  * Node Name: `http://host.docker.internal:8001/auth`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/auth/
  * Node Name: `http://host.docker.internal:8001/auth/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/auth/1641733886319771715
  * Node Name: `http://host.docker.internal:8001/auth/1641733886319771715`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/6376536506649367530
  * Node Name: `http://host.docker.internal:8001/clients/6376536506649367530`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/client_id
  * Node Name: `http://host.docker.internal:8001/clients/client_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/client_id/
  * Node Name: `http://host.docker.internal:8001/clients/client_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/client_id/2183776063063557868
  * Node Name: `http://host.docker.internal:8001/clients/client_id/2183776063063557868`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/client_id/signatories
  * Node Name: `http://host.docker.internal:8001/clients/client_id/signatories`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/client_id/signatories%3Finclude_inactive=false
  * Node Name: `http://host.docker.internal:8001/clients/client_id/signatories (include_inactive)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/client_id/signatories/
  * Node Name: `http://host.docker.internal:8001/clients/client_id/signatories/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/client_id/signatories/4549996953490878595
  * Node Name: `http://host.docker.internal:8001/clients/client_id/signatories/4549996953490878595`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/type-defaults
  * Node Name: `http://host.docker.internal:8001/clients/type-defaults`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/type-defaults/
  * Node Name: `http://host.docker.internal:8001/clients/type-defaults/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/type-defaults/4815304724098859867
  * Node Name: `http://host.docker.internal:8001/clients/type-defaults/4815304724098859867`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/company
  * Node Name: `http://host.docker.internal:8001/company`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/company/
  * Node Name: `http://host.docker.internal:8001/company/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/company/7270851563486395111
  * Node Name: `http://host.docker.internal:8001/company/7270851563486395111`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/company/logo/2277855942284512307
  * Node Name: `http://host.docker.internal:8001/company/logo/2277855942284512307`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/construction-sequence%3Fsport_id=
  * Node Name: `http://host.docker.internal:8001/construction-sequence (sport_id)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/construction-sequence/4541996362203663703
  * Node Name: `http://host.docker.internal:8001/construction-sequence/4541996362203663703`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/construction-sequence/draft
  * Node Name: `http://host.docker.internal:8001/construction-sequence/draft`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/construction-sequence/draft/
  * Node Name: `http://host.docker.internal:8001/construction-sequence/draft/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/construction-sequence/draft/4995081336722753209
  * Node Name: `http://host.docker.internal:8001/construction-sequence/draft/4995081336722753209`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets
  * Node Name: `http://host.docker.internal:8001/cost-sheets`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/5625437761546488007
  * Node Name: `http://host.docker.internal:8001/cost-sheets/5625437761546488007`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/1749297794052965707
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/1749297794052965707`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/consumption-sheet
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/consumption-sheet`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/consumption-sheet/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/consumption-sheet/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/exports
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/exports`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/exports/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/exports/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/exports/3717105406438153833
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/exports/3717105406438153833`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/exports/bom
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/exports/bom`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/exports/bom/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/exports/bom/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/exports/consumption-sheet
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/exports/consumption-sheet`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/exports/consumption-sheet/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/exports/consumption-sheet/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/exports/cost-sheet
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/exports/cost-sheet`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/exports/cost-sheet/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/exports/cost-sheet/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/exports/rfq
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/exports/rfq`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/exports/rfq/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/exports/rfq/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/3609146217089921207
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/3609146217089921207`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/k1-constants
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/k1-constants`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/k1-constants/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/k1-constants/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/labour-warnings
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/labour-warnings`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/labour-warnings/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/labour-warnings/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/lines
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/lines`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/lines/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/lines/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/lines/7616611755676787037
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/lines/7616611755676787037`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/purchase-orders
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/purchase-orders`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/purchase-orders/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/purchase-orders/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cross-sell-addons
  * Node Name: `http://host.docker.internal:8001/cross-sell-addons`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cross-sell-addons/
  * Node Name: `http://host.docker.internal:8001/cross-sell-addons/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cross-sell-addons/7769210128834380356
  * Node Name: `http://host.docker.internal:8001/cross-sell-addons/7769210128834380356`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cross-sell-addons/addon_id
  * Node Name: `http://host.docker.internal:8001/cross-sell-addons/addon_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cross-sell-addons/addon_id/
  * Node Name: `http://host.docker.internal:8001/cross-sell-addons/addon_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cross-sell-addons/addon_id/2736023850190214100
  * Node Name: `http://host.docker.internal:8001/cross-sell-addons/addon_id/2736023850190214100`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cross-sell-addons/suggestions
  * Node Name: `http://host.docker.internal:8001/cross-sell-addons/suggestions`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cross-sell-addons/suggestions/
  * Node Name: `http://host.docker.internal:8001/cross-sell-addons/suggestions/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cross-sell-addons/suggestions/3257545087512302371
  * Node Name: `http://host.docker.internal:8001/cross-sell-addons/suggestions/3257545087512302371`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cross-sell-addons/suggestions/for-project
  * Node Name: `http://host.docker.internal:8001/cross-sell-addons/suggestions/for-project`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cross-sell-addons/suggestions/for-project/
  * Node Name: `http://host.docker.internal:8001/cross-sell-addons/suggestions/for-project/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cross-sell-addons/suggestions/for-project/1745557524957817547
  * Node Name: `http://host.docker.internal:8001/cross-sell-addons/suggestions/for-project/1745557524957817547`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cross-sell-addons/suggestions/for-project/project_id
  * Node Name: `http://host.docker.internal:8001/cross-sell-addons/suggestions/for-project/project_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cross-sell-addons/suggestions/for-project/project_id/
  * Node Name: `http://host.docker.internal:8001/cross-sell-addons/suggestions/for-project/project_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/education
  * Node Name: `http://host.docker.internal:8001/education`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/education/
  * Node Name: `http://host.docker.internal:8001/education/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/education/8948705415231873792
  * Node Name: `http://host.docker.internal:8001/education/8948705415231873792`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimate-option-addons
  * Node Name: `http://host.docker.internal:8001/estimate-option-addons`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimate-option-addons/
  * Node Name: `http://host.docker.internal:8001/estimate-option-addons/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimate-option-addons/3507307814923233134
  * Node Name: `http://host.docker.internal:8001/estimate-option-addons/3507307814923233134`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimate-options
  * Node Name: `http://host.docker.internal:8001/estimate-options`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimate-options/
  * Node Name: `http://host.docker.internal:8001/estimate-options/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimate-options/3697451762555056057
  * Node Name: `http://host.docker.internal:8001/estimate-options/3697451762555056057`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimate-options/option_id
  * Node Name: `http://host.docker.internal:8001/estimate-options/option_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimate-options/option_id/
  * Node Name: `http://host.docker.internal:8001/estimate-options/option_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimate-options/option_id/6431488957762893453
  * Node Name: `http://host.docker.internal:8001/estimate-options/option_id/6431488957762893453`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimate-options/option_id/addons
  * Node Name: `http://host.docker.internal:8001/estimate-options/option_id/addons`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimate-options/option_id/addons/
  * Node Name: `http://host.docker.internal:8001/estimate-options/option_id/addons/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates%3Fsearch=ZAP&status=
  * Node Name: `http://host.docker.internal:8001/estimates (search,status)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/263500469959314654
  * Node Name: `http://host.docker.internal:8001/estimates/263500469959314654`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/estimate_id
  * Node Name: `http://host.docker.internal:8001/estimates/estimate_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/estimate_id/
  * Node Name: `http://host.docker.internal:8001/estimates/estimate_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/estimate_id/2537350094407935784
  * Node Name: `http://host.docker.internal:8001/estimates/estimate_id/2537350094407935784`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/estimate_id/options
  * Node Name: `http://host.docker.internal:8001/estimates/estimate_id/options`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/estimate_id/options/
  * Node Name: `http://host.docker.internal:8001/estimates/estimate_id/options/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/estimate_id/options/8546590393010866456
  * Node Name: `http://host.docker.internal:8001/estimates/estimate_id/options/8546590393010866456`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/estimate_id/options/option_id
  * Node Name: `http://host.docker.internal:8001/estimates/estimate_id/options/option_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/estimate_id/options/option_id/
  * Node Name: `http://host.docker.internal:8001/estimates/estimate_id/options/option_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/estimate_id/options/option_id/2081631714237768396
  * Node Name: `http://host.docker.internal:8001/estimates/estimate_id/options/option_id/2081631714237768396`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/estimate_id/pdf
  * Node Name: `http://host.docker.internal:8001/estimates/estimate_id/pdf`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/estimate_id/pdf/
  * Node Name: `http://host.docker.internal:8001/estimates/estimate_id/pdf/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/field-settings/8464722509670293050
  * Node Name: `http://host.docker.internal:8001/field-settings/8464722509670293050`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/flooring-guides%3Fsport_id=
  * Node Name: `http://host.docker.internal:8001/flooring-guides (sport_id)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/flooring-guides/3199612136093745039
  * Node Name: `http://host.docker.internal:8001/flooring-guides/3199612136093745039`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/hubs%3Finclude_inactive=http%253A%252F%252Fwww.google.com%252F
  * Node Name: `http://host.docker.internal:8001/hubs (include_inactive)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/hubs/8674196049971815896
  * Node Name: `http://host.docker.internal:8001/hubs/8674196049971815896`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/integrations
  * Node Name: `http://host.docker.internal:8001/integrations`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/integrations/
  * Node Name: `http://host.docker.internal:8001/integrations/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/integrations/6451731896290691192
  * Node Name: `http://host.docker.internal:8001/integrations/6451731896290691192`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/integrations/wa-gateway
  * Node Name: `http://host.docker.internal:8001/integrations/wa-gateway`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/integrations/wa-gateway/
  * Node Name: `http://host.docker.internal:8001/integrations/wa-gateway/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/integrations/wa-gateway/7514257675190964713
  * Node Name: `http://host.docker.internal:8001/integrations/wa-gateway/7514257675190964713`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/labour-categories
  * Node Name: `http://host.docker.internal:8001/labour-categories`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/labour-categories/
  * Node Name: `http://host.docker.internal:8001/labour-categories/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/lighting-standards
  * Node Name: `http://host.docker.internal:8001/lighting-standards`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/lighting-standards/
  * Node Name: `http://host.docker.internal:8001/lighting-standards/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/lighting-standards/2488848841291258599
  * Node Name: `http://host.docker.internal:8001/lighting-standards/2488848841291258599`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/lighting-standards/lux/936277807960022546
  * Node Name: `http://host.docker.internal:8001/lighting-standards/lux/936277807960022546`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/lighting-standards/pole-counts%3Fsport_id=
  * Node Name: `http://host.docker.internal:8001/lighting-standards/pole-counts (sport_id)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/lighting-standards/pole-counts/3721291843533057711
  * Node Name: `http://host.docker.internal:8001/lighting-standards/pole-counts/3721291843533057711`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/margin-policies
  * Node Name: `http://host.docker.internal:8001/margin-policies`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/margin-policies/
  * Node Name: `http://host.docker.internal:8001/margin-policies/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/message-templates%3Fchannel=&document_type=&include_inactive=false
  * Node Name: `http://host.docker.internal:8001/message-templates (channel,document_type,include_inactive)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/message-templates/6395005817689756352
  * Node Name: `http://host.docker.internal:8001/message-templates/6395005817689756352`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/messages
  * Node Name: `http://host.docker.internal:8001/messages`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/messages%3Fdoc_type=cost_sheet&doc_id=doc_id
  * Node Name: `http://host.docker.internal:8001/messages (doc_id,doc_type)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/messages/
  * Node Name: `http://host.docker.internal:8001/messages/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/messages/1662568142169314320
  * Node Name: `http://host.docker.internal:8001/messages/1662568142169314320`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/netting-grades
  * Node Name: `http://host.docker.internal:8001/netting-grades`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/netting-grades%3Finclude_inactive=false
  * Node Name: `http://host.docker.internal:8001/netting-grades (include_inactive)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/netting-grades/
  * Node Name: `http://host.docker.internal:8001/netting-grades/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/netting-grades/6190590490771995573
  * Node Name: `http://host.docker.internal:8001/netting-grades/6190590490771995573`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/opportunities%3Fstage=&relationship=
  * Node Name: `http://host.docker.internal:8001/opportunities (relationship,stage)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/opportunities/7850270006976097454
  * Node Name: `http://host.docker.internal:8001/opportunities/7850270006976097454`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/opportunities/opportunity_id
  * Node Name: `http://host.docker.internal:8001/opportunities/opportunity_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/opportunities/opportunity_id/
  * Node Name: `http://host.docker.internal:8001/opportunities/opportunity_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/opportunities/opportunity_id/4142826905490571020
  * Node Name: `http://host.docker.internal:8001/opportunities/opportunity_id/4142826905490571020`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/overrides
  * Node Name: `http://host.docker.internal:8001/overrides`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/overrides%3Fdocument_type=cost_sheet&document_id=document_id
  * Node Name: `http://host.docker.internal:8001/overrides (document_id,document_type)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/overrides/
  * Node Name: `http://host.docker.internal:8001/overrides/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/package-contents%3Fsport_id=
  * Node Name: `http://host.docker.internal:8001/package-contents (sport_id)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/package-contents/484530789699219345
  * Node Name: `http://host.docker.internal:8001/package-contents/484530789699219345`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/package-contents/sport_id
  * Node Name: `http://host.docker.internal:8001/package-contents/sport_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/package-contents/sport_id/
  * Node Name: `http://host.docker.internal:8001/package-contents/sport_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/package-contents/sport_id/8122677312948901196
  * Node Name: `http://host.docker.internal:8001/package-contents/sport_id/8122677312948901196`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/payment-entries
  * Node Name: `http://host.docker.internal:8001/payment-entries`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/payment-entries/
  * Node Name: `http://host.docker.internal:8001/payment-entries/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/payment-entries/3051158038755266892
  * Node Name: `http://host.docker.internal:8001/payment-entries/3051158038755266892`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/payment-milestones
  * Node Name: `http://host.docker.internal:8001/payment-milestones`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/payment-milestones/
  * Node Name: `http://host.docker.internal:8001/payment-milestones/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/payment-milestones/8916075753874400230
  * Node Name: `http://host.docker.internal:8001/payment-milestones/8916075753874400230`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/payments
  * Node Name: `http://host.docker.internal:8001/payments`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/payments%3Foverdue=&search=ZAP
  * Node Name: `http://host.docker.internal:8001/payments (overdue,search)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/payments/
  * Node Name: `http://host.docker.internal:8001/payments/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/price-requests
  * Node Name: `http://host.docker.internal:8001/price-requests`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/price-requests%3Fstatus=&overdue_only=false
  * Node Name: `http://host.docker.internal:8001/price-requests (overdue_only,status)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/price-requests/
  * Node Name: `http://host.docker.internal:8001/price-requests/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/price-requests/5993932696184376661
  * Node Name: `http://host.docker.internal:8001/price-requests/5993932696184376661`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/price-requests/price_request_id
  * Node Name: `http://host.docker.internal:8001/price-requests/price_request_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/price-requests/price_request_id/
  * Node Name: `http://host.docker.internal:8001/price-requests/price_request_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/price-requests/price_request_id/4375758788715919369
  * Node Name: `http://host.docker.internal:8001/price-requests/price_request_id/4375758788715919369`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/price-requests/price_request_id/items
  * Node Name: `http://host.docker.internal:8001/price-requests/price_request_id/items`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/price-requests/price_request_id/items/
  * Node Name: `http://host.docker.internal:8001/price-requests/price_request_id/items/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/price-requests/price_request_id/items/1967548216901076355
  * Node Name: `http://host.docker.internal:8001/price-requests/price_request_id/items/1967548216901076355`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/price-requests/price_request_id/items/item_id
  * Node Name: `http://host.docker.internal:8001/price-requests/price_request_id/items/item_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/price-requests/price_request_id/items/item_id/
  * Node Name: `http://host.docker.internal:8001/price-requests/price_request_id/items/item_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/price-requests/price_request_id/items/item_id/2955034639717287506
  * Node Name: `http://host.docker.internal:8001/price-requests/price_request_id/items/item_id/2955034639717287506`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/price-requests/price_request_id/items/item_id/replies
  * Node Name: `http://host.docker.internal:8001/price-requests/price_request_id/items/item_id/replies`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/price-requests/price_request_id/items/item_id/replies/
  * Node Name: `http://host.docker.internal:8001/price-requests/price_request_id/items/item_id/replies/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/pricing
  * Node Name: `http://host.docker.internal:8001/pricing`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/pricing/
  * Node Name: `http://host.docker.internal:8001/pricing/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/pricing/8924856473521407977
  * Node Name: `http://host.docker.internal:8001/pricing/8924856473521407977`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/products
  * Node Name: `http://host.docker.internal:8001/products`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/products/
  * Node Name: `http://host.docker.internal:8001/products/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/products/1316060674674886104
  * Node Name: `http://host.docker.internal:8001/products/1316060674674886104`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects%3Fsearch=ZAP&status=&client_id=
  * Node Name: `http://host.docker.internal:8001/projects (client_id,search,status)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/3022048526325947601
  * Node Name: `http://host.docker.internal:8001/projects/3022048526325947601`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id
  * Node Name: `http://host.docker.internal:8001/projects/project_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/7630564988412279411
  * Node Name: `http://host.docker.internal:8001/projects/project_id/7630564988412279411`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/cost-sheets
  * Node Name: `http://host.docker.internal:8001/projects/project_id/cost-sheets`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/cost-sheets/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/cost-sheets/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/estimates
  * Node Name: `http://host.docker.internal:8001/projects/project_id/estimates`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/estimates/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/estimates/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/quotations
  * Node Name: `http://host.docker.internal:8001/projects/project_id/quotations`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/quotations/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/quotations/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/quotations/7065365069245039200
  * Node Name: `http://host.docker.internal:8001/projects/project_id/quotations/7065365069245039200`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/scope-items
  * Node Name: `http://host.docker.internal:8001/projects/project_id/scope-items`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/scope-items/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/scope-items/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/scope-items/4284919293755024951
  * Node Name: `http://host.docker.internal:8001/projects/project_id/scope-items/4284919293755024951`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/site-surveys
  * Node Name: `http://host.docker.internal:8001/projects/project_id/site-surveys`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/site-surveys/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/site-surveys/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/skip-requests
  * Node Name: `http://host.docker.internal:8001/projects/project_id/skip-requests`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/skip-requests/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/skip-requests/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/sports
  * Node Name: `http://host.docker.internal:8001/projects/project_id/sports`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/sports/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/sports/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/sports/3688897895633290508
  * Node Name: `http://host.docker.internal:8001/projects/project_id/sports/3688897895633290508`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/sports/selection_id
  * Node Name: `http://host.docker.internal:8001/projects/project_id/sports/selection_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/sports/selection_id/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/sports/selection_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/sports/selection_id/7760946230321017098
  * Node Name: `http://host.docker.internal:8001/projects/project_id/sports/selection_id/7760946230321017098`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/technical-bid-checklist
  * Node Name: `http://host.docker.internal:8001/projects/project_id/technical-bid-checklist`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/technical-bid-checklist/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/technical-bid-checklist/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/technical-bid-checklist/7435502020231559407
  * Node Name: `http://host.docker.internal:8001/projects/project_id/technical-bid-checklist/7435502020231559407`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/tender-details
  * Node Name: `http://host.docker.internal:8001/projects/project_id/tender-details`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/tender-details/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/tender-details/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/tender-details/6344881861862503383
  * Node Name: `http://host.docker.internal:8001/projects/project_id/tender-details/6344881861862503383`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/tender-details/competitor-bids
  * Node Name: `http://host.docker.internal:8001/projects/project_id/tender-details/competitor-bids`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/tender-details/competitor-bids/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/tender-details/competitor-bids/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/tender-details/competitor-bids/8217750641708813614
  * Node Name: `http://host.docker.internal:8001/projects/project_id/tender-details/competitor-bids/8217750641708813614`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/purchase-orders
  * Node Name: `http://host.docker.internal:8001/purchase-orders`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/purchase-orders/
  * Node Name: `http://host.docker.internal:8001/purchase-orders/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/purchase-orders/6815219873732229666
  * Node Name: `http://host.docker.internal:8001/purchase-orders/6815219873732229666`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/purchase-orders/po_id
  * Node Name: `http://host.docker.internal:8001/purchase-orders/po_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/purchase-orders/po_id/
  * Node Name: `http://host.docker.internal:8001/purchase-orders/po_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/purchase-orders/po_id/7642418659618090767
  * Node Name: `http://host.docker.internal:8001/purchase-orders/po_id/7642418659618090767`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotation-template-defaults
  * Node Name: `http://host.docker.internal:8001/quotation-template-defaults`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotation-template-defaults/
  * Node Name: `http://host.docker.internal:8001/quotation-template-defaults/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations%3Fstatus=&status_group=&project_id=&client_id=&date_from=&date_to=
  * Node Name: `http://host.docker.internal:8001/quotations (client_id,date_from,date_to,project_id,status,status_group)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/2098088320558571010
  * Node Name: `http://host.docker.internal:8001/quotations/2098088320558571010`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/export
  * Node Name: `http://host.docker.internal:8001/quotations/export`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/export%3Fstatus=&status_group=&project_id=&client_id=&date_from=&date_to=
  * Node Name: `http://host.docker.internal:8001/quotations/export (client_id,date_from,date_to,project_id,status,status_group)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/export/
  * Node Name: `http://host.docker.internal:8001/quotations/export/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/1361248633587980515
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/1361248633587980515`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/exports
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/exports`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/exports/
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/exports/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/exports/9053952826537090102
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/exports/9053952826537090102`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/exports/billing-handoff
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/exports/billing-handoff`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/exports/billing-handoff/
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/exports/billing-handoff/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/l1-view
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/l1-view`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/l1-view/
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/l1-view/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/pdf
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/pdf`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/pdf/
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/pdf/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/work-order
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/work-order`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/work-order/
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/work-order/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items
  * Node Name: `http://host.docker.internal:8001/rate-items`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items%3Fwatched_only=false
  * Node Name: `http://host.docker.internal:8001/rate-items (watched_only)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/
  * Node Name: `http://host.docker.internal:8001/rate-items/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/4281627882463123939
  * Node Name: `http://host.docker.internal:8001/rate-items/4281627882463123939`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/export
  * Node Name: `http://host.docker.internal:8001/rate-items/export`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/export/
  * Node Name: `http://host.docker.internal:8001/rate-items/export/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/rate_item_id
  * Node Name: `http://host.docker.internal:8001/rate-items/rate_item_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/rate_item_id/
  * Node Name: `http://host.docker.internal:8001/rate-items/rate_item_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/rate_item_id/4517136099909670039
  * Node Name: `http://host.docker.internal:8001/rate-items/rate_item_id/4517136099909670039`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/rate_item_id/history
  * Node Name: `http://host.docker.internal:8001/rate-items/rate_item_id/history`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/rate_item_id/history/
  * Node Name: `http://host.docker.internal:8001/rate-items/rate_item_id/history/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/reports/954329635791108114
  * Node Name: `http://host.docker.internal:8001/reports/954329635791108114`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/reports/report_id
  * Node Name: `http://host.docker.internal:8001/reports/report_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/reports/report_id/
  * Node Name: `http://host.docker.internal:8001/reports/report_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/reports/report_id/1024032087745481569
  * Node Name: `http://host.docker.internal:8001/reports/report_id/1024032087745481569`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/reports/report_id/export
  * Node Name: `http://host.docker.internal:8001/reports/report_id/export`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/reports/report_id/export/
  * Node Name: `http://host.docker.internal:8001/reports/report_id/export/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/reports/report_id/pdf
  * Node Name: `http://host.docker.internal:8001/reports/report_id/pdf`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/reports/report_id/pdf/
  * Node Name: `http://host.docker.internal:8001/reports/report_id/pdf/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/role-permissions
  * Node Name: `http://host.docker.internal:8001/role-permissions`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/role-permissions/
  * Node Name: `http://host.docker.internal:8001/role-permissions/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/schedule
  * Node Name: `http://host.docker.internal:8001/schedule`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/schedule/
  * Node Name: `http://host.docker.internal:8001/schedule/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/schedule/3011615402325613143
  * Node Name: `http://host.docker.internal:8001/schedule/3011615402325613143`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/schedule/project-sports
  * Node Name: `http://host.docker.internal:8001/schedule/project-sports`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/schedule/project-sports/
  * Node Name: `http://host.docker.internal:8001/schedule/project-sports/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/schedule/project-sports/666327186104908565
  * Node Name: `http://host.docker.internal:8001/schedule/project-sports/666327186104908565`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/schedule/project-sports/project_sport_id
  * Node Name: `http://host.docker.internal:8001/schedule/project-sports/project_sport_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/schedule/project-sports/project_sport_id%3Fstart_date=&mobilisation_days=
  * Node Name: `http://host.docker.internal:8001/schedule/project-sports/project_sport_id (mobilisation_days,start_date)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/schedule/project-sports/project_sport_id/
  * Node Name: `http://host.docker.internal:8001/schedule/project-sports/project_sport_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/scope-items%3Finclude_inactive=http%253A%252F%252Fwww.google.com%252F
  * Node Name: `http://host.docker.internal:8001/scope-items (include_inactive)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/scope-items/5567210804242542376
  * Node Name: `http://host.docker.internal:8001/scope-items/5567210804242542376`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/search
  * Node Name: `http://host.docker.internal:8001/search`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/search%3Fq=q
  * Node Name: `http://host.docker.internal:8001/search (q)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/search/
  * Node Name: `http://host.docker.internal:8001/search/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/settings
  * Node Name: `http://host.docker.internal:8001/settings`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/settings/
  * Node Name: `http://host.docker.internal:8001/settings/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/settings/7941092340249467694
  * Node Name: `http://host.docker.internal:8001/settings/7941092340249467694`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/settings/export
  * Node Name: `http://host.docker.internal:8001/settings/export`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/settings/export/
  * Node Name: `http://host.docker.internal:8001/settings/export/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/settings/key
  * Node Name: `http://host.docker.internal:8001/settings/key`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/settings/key/
  * Node Name: `http://host.docker.internal:8001/settings/key/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/settings/key/3923753616645690440
  * Node Name: `http://host.docker.internal:8001/settings/key/3923753616645690440`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/settings/key/history
  * Node Name: `http://host.docker.internal:8001/settings/key/history`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/settings/key/history%3Fscope_value=
  * Node Name: `http://host.docker.internal:8001/settings/key/history (scope_value)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/settings/key/history/
  * Node Name: `http://host.docker.internal:8001/settings/key/history/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/site-surveys
  * Node Name: `http://host.docker.internal:8001/site-surveys`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/site-surveys/
  * Node Name: `http://host.docker.internal:8001/site-surveys/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/site-surveys/6009472783009959737
  * Node Name: `http://host.docker.internal:8001/site-surveys/6009472783009959737`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/site-surveys/site_survey_id
  * Node Name: `http://host.docker.internal:8001/site-surveys/site_survey_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/site-surveys/site_survey_id/
  * Node Name: `http://host.docker.internal:8001/site-surveys/site_survey_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/site-surveys/site_survey_id/525570788230398740
  * Node Name: `http://host.docker.internal:8001/site-surveys/site_survey_id/525570788230398740`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/skip-requests
  * Node Name: `http://host.docker.internal:8001/skip-requests`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/skip-requests/
  * Node Name: `http://host.docker.internal:8001/skip-requests/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/skip-requests/335435206174281844
  * Node Name: `http://host.docker.internal:8001/skip-requests/335435206174281844`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/skip-requests/skip_request_id
  * Node Name: `http://host.docker.internal:8001/skip-requests/skip_request_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/skip-requests/skip_request_id/
  * Node Name: `http://host.docker.internal:8001/skip-requests/skip_request_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/skip-requests/skip_request_id/2339922932536063082
  * Node Name: `http://host.docker.internal:8001/skip-requests/skip_request_id/2339922932536063082`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/sport-margin-policies
  * Node Name: `http://host.docker.internal:8001/sport-margin-policies`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/sport-margin-policies/
  * Node Name: `http://host.docker.internal:8001/sport-margin-policies/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/sport-margin-policies/2064159664137407099
  * Node Name: `http://host.docker.internal:8001/sport-margin-policies/2064159664137407099`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/sports%3Finclude_inactive=http%253A%252F%252Fwww.google.com%252F
  * Node Name: `http://host.docker.internal:8001/sports (include_inactive)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/sports/886266164179771101
  * Node Name: `http://host.docker.internal:8001/sports/886266164179771101`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/tender
  * Node Name: `http://host.docker.internal:8001/tender`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/tender/
  * Node Name: `http://host.docker.internal:8001/tender/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/tender/8005680166600853900
  * Node Name: `http://host.docker.internal:8001/tender/8005680166600853900`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/users
  * Node Name: `http://host.docker.internal:8001/users`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/users/
  * Node Name: `http://host.docker.internal:8001/users/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/users/3632322875975879715
  * Node Name: `http://host.docker.internal:8001/users/3632322875975879715`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/users/user_id
  * Node Name: `http://host.docker.internal:8001/users/user_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/users/user_id/
  * Node Name: `http://host.docker.internal:8001/users/user_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/users/user_id/8129302224743538661
  * Node Name: `http://host.docker.internal:8001/users/user_id/8129302224743538661`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vehicle-classes
  * Node Name: `http://host.docker.internal:8001/vehicle-classes`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vehicle-classes%3Finclude_inactive=false
  * Node Name: `http://host.docker.internal:8001/vehicle-classes (include_inactive)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vehicle-classes/
  * Node Name: `http://host.docker.internal:8001/vehicle-classes/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vehicle-classes/3032541503243908331
  * Node Name: `http://host.docker.internal:8001/vehicle-classes/3032541503243908331`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vendor-replies
  * Node Name: `http://host.docker.internal:8001/vendor-replies`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vendor-replies/
  * Node Name: `http://host.docker.internal:8001/vendor-replies/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vendor-replies/3983613112436708654
  * Node Name: `http://host.docker.internal:8001/vendor-replies/3983613112436708654`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vendor-replies/reply_id
  * Node Name: `http://host.docker.internal:8001/vendor-replies/reply_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vendor-replies/reply_id/
  * Node Name: `http://host.docker.internal:8001/vendor-replies/reply_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vendor-replies/reply_id/4723055804455329772
  * Node Name: `http://host.docker.internal:8001/vendor-replies/reply_id/4723055804455329772`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vendors
  * Node Name: `http://host.docker.internal:8001/vendors`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vendors%3Finclude_inactive=false
  * Node Name: `http://host.docker.internal:8001/vendors (include_inactive)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vendors/
  * Node Name: `http://host.docker.internal:8001/vendors/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vendors/8712756215067847064
  * Node Name: `http://host.docker.internal:8001/vendors/8712756215067847064`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vendors/vendor_id
  * Node Name: `http://host.docker.internal:8001/vendors/vendor_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vendors/vendor_id/
  * Node Name: `http://host.docker.internal:8001/vendors/vendor_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vendors/vendor_id/9089215789377701423
  * Node Name: `http://host.docker.internal:8001/vendors/vendor_id/9089215789377701423`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vendors/vendor_id/products
  * Node Name: `http://host.docker.internal:8001/vendors/vendor_id/products`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vendors/vendor_id/products/
  * Node Name: `http://host.docker.internal:8001/vendors/vendor_id/products/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/work-orders
  * Node Name: `http://host.docker.internal:8001/work-orders`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/work-orders/
  * Node Name: `http://host.docker.internal:8001/work-orders/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/work-orders/5201291877794964697
  * Node Name: `http://host.docker.internal:8001/work-orders/5201291877794964697`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/work-orders/work_order_id
  * Node Name: `http://host.docker.internal:8001/work-orders/work_order_id`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/work-orders/work_order_id/
  * Node Name: `http://host.docker.internal:8001/work-orders/work_order_id/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://host.docker.internal:8001/work-orders/work_order_id/3661157493765032284
  * Node Name: `http://host.docker.internal:8001/work-orders/work_order_id/3661157493765032284`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/work-orders/work_order_id/payment-entries
  * Node Name: `http://host.docker.internal:8001/work-orders/work_order_id/payment-entries`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/work-orders/work_order_id/payment-entries/
  * Node Name: `http://host.docker.internal:8001/work-orders/work_order_id/payment-entries/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/work-orders/work_order_id/payment-milestones
  * Node Name: `http://host.docker.internal:8001/work-orders/work_order_id/payment-milestones`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/work-orders/work_order_id/payment-milestones/
  * Node Name: `http://host.docker.internal:8001/work-orders/work_order_id/payment-milestones/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/work-orders/work_order_id/payment-summary
  * Node Name: `http://host.docker.internal:8001/work-orders/work_order_id/payment-summary`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/work-orders/work_order_id/payment-summary/
  * Node Name: `http://host.docker.internal:8001/work-orders/work_order_id/payment-summary/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/accessory-catalog/item_id
  * Node Name: `http://host.docker.internal:8001/accessory-catalog/item_id ()({item_name,unit,quantity_per_court,is_active})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/accessory-catalog/item_id/
  * Node Name: `http://host.docker.internal:8001/accessory-catalog/item_id/ ()({item_name,unit,quantity_per_court,is_active})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/client_id
  * Node Name: `http://host.docker.internal:8001/clients/client_id ()({overdue_flag,blacklist_flag})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/client_id/
  * Node Name: `http://host.docker.internal:8001/clients/client_id/ ()({overdue_flag,blacklist_flag})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/client_id/consent
  * Node Name: `http://host.docker.internal:8001/clients/client_id/consent ()({whatsapp_opt_in,email_opt_in,consent_date,telegram_opt_in,telegram_chat_id})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/client_id/consent/
  * Node Name: `http://host.docker.internal:8001/clients/client_id/consent/ ()({whatsapp_opt_in,email_opt_in,consent_date,telegram_opt_in,telegram_chat_id})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/client_id/details
  * Node Name: `http://host.docker.internal:8001/clients/client_id/details ()({"name":"ZAP","contact_name":"John Doe","phone":9999999999,"email":zaproxy@example.com,"city":East Romaineburgh})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/client_id/details/
  * Node Name: `http://host.docker.internal:8001/clients/client_id/details/ ()({"name":"ZAP","contact_name":"John Doe","phone":9999999999,"email":zaproxy@example.com,"city":East Romaineburgh})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/client_id/follow-up
  * Node Name: `http://host.docker.internal:8001/clients/client_id/follow-up ()({next_follow_up_date,follow_up_note})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/client_id/follow-up/
  * Node Name: `http://host.docker.internal:8001/clients/client_id/follow-up/ ()({next_follow_up_date,follow_up_note})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/client_id/notes
  * Node Name: `http://host.docker.internal:8001/clients/client_id/notes ()({notes})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/client_id/notes/
  * Node Name: `http://host.docker.internal:8001/clients/client_id/notes/ ()({notes})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/client_id/signatories/signatory_id
  * Node Name: `http://host.docker.internal:8001/clients/client_id/signatories/signatory_id ()({"name":ZAP,"designation":"John Doe","email":zaproxy@example.com,"phone":9999999999,"authorization_date":"1970-01-01","authorization_doc_attachment_id":"John Doe","expiry_date":"1970-01-01","is_active":true})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/client_id/signatories/signatory_id/
  * Node Name: `http://host.docker.internal:8001/clients/client_id/signatories/signatory_id/ ()({"name":ZAP,"designation":"John Doe","email":zaproxy@example.com,"phone":9999999999,"authorization_date":"1970-01-01","authorization_doc_attachment_id":"John Doe","expiry_date":"1970-01-01","is_active":true})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/computeMetadata/v1/
  * Node Name: `http://host.docker.internal:8001/computeMetadata/v1/ ()({item_name,unit,quantity_per_court,is_active})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/lines/line_id
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/lines/line_id ()({work_package,category,item_name,spec,unit,quantity,rate,city_of_quote,labour_category_id,wastage_percent})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/lines/line_id/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/lines/line_id/ ()({work_package,category,item_name,spec,unit,quantity,rate,city_of_quote,labour_category_id,wastage_percent})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cross-sell-addons/addon_id
  * Node Name: `http://host.docker.internal:8001/cross-sell-addons/addon_id ()({"name":ZAP,"category":"lighting","description":Zaproxy alias impedit expedita quisquam pariatur exercitationem. Nemo rerum eveniet dolores rem quia dignissimos.,"cost":1.2,"unit":"John Doe","margin_percent":1.2,"all_sports":true,"is_active":true})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cross-sell-addons/addon_id/
  * Node Name: `http://host.docker.internal:8001/cross-sell-addons/addon_id/ ()({"name":ZAP,"category":"lighting","description":Zaproxy alias impedit expedita quisquam pariatur exercitationem. Nemo rerum eveniet dolores rem quia dignissimos.,"cost":1.2,"unit":"John Doe","margin_percent":1.2,"all_sports":true,"is_active":true})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/estimate_id/options/option_id/client-status
  * Node Name: `http://host.docker.internal:8001/estimates/estimate_id/options/option_id/client-status ()({client_status,client_demand_note,waive_evidence_reason,rejection_reason})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/estimate_id/options/option_id/client-status/
  * Node Name: `http://host.docker.internal:8001/estimates/estimate_id/options/option_id/client-status/ ()({client_status,client_demand_note,waive_evidence_reason,rejection_reason})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/field-settings/field_key
  * Node Name: `http://host.docker.internal:8001/field-settings/field_key ()({state})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/field-settings/field_key/
  * Node Name: `http://host.docker.internal:8001/field-settings/field_key/ ()({state})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/hubs/hub_id
  * Node Name: `http://host.docker.internal:8001/hubs/hub_id ()({"name":ZAP,"city":East Romaineburgh,"state_code":"John Doe","is_active":true})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/hubs/hub_id/
  * Node Name: `http://host.docker.internal:8001/hubs/hub_id/ ()({"name":ZAP,"city":East Romaineburgh,"state_code":"John Doe","is_active":true})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/latest/meta-data/
  * Node Name: `http://host.docker.internal:8001/latest/meta-data/ ()({item_name,unit,quantity_per_court,is_active})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/message-templates/template_id
  * Node Name: `http://host.docker.internal:8001/message-templates/template_id ()({"document_type":"cost_sheet","name":ZAP,"subject":Zaproxy dolore alias impedit expedita quisquam.,"body":"John Doe","language":en,"whatsapp_template_status":"draft","is_active":true})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/message-templates/template_id/
  * Node Name: `http://host.docker.internal:8001/message-templates/template_id/ ()({"document_type":"cost_sheet","name":ZAP,"subject":Zaproxy dolore alias impedit expedita quisquam.,"body":"John Doe","language":en,"whatsapp_template_status":"draft","is_active":true})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/metadata/instance
  * Node Name: `http://host.docker.internal:8001/metadata/instance ()({item_name,unit,quantity_per_court,is_active})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/metadata/v1
  * Node Name: `http://host.docker.internal:8001/metadata/v1 ()({item_name,unit,quantity_per_court,is_active})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/netting-grades/grade_id
  * Node Name: `http://host.docker.internal:8001/netting-grades/grade_id ()({"name":ZAP,"material":"John Doe","twine":"John Doe","mesh":"John Doe","uv_stabilized":true,"typical_use":"John Doe","rate_per_sqm":1.2,"is_active":true})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/netting-grades/grade_id/
  * Node Name: `http://host.docker.internal:8001/netting-grades/grade_id/ ()({"name":ZAP,"material":"John Doe","twine":"John Doe","mesh":"John Doe","uv_stabilized":true,"typical_use":"John Doe","rate_per_sqm":1.2,"is_active":true})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/opc/v1/instance/
  * Node Name: `http://host.docker.internal:8001/opc/v1/instance/ ()({item_name,unit,quantity_per_court,is_active})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/opc/v2/instance/
  * Node Name: `http://host.docker.internal:8001/opc/v2/instance/ ()({item_name,unit,quantity_per_court,is_active})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/openstack/latest/meta_data.json
  * Node Name: `http://host.docker.internal:8001/openstack/latest/meta_data.json ()({item_name,unit,quantity_per_court,is_active})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://host.docker.internal:8001/opportunities/opportunity_id/details
  * Node Name: `http://host.docker.internal:8001/opportunities/opportunity_id/details ()({lead_name,lead_phone,lead_email})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/opportunities/opportunity_id/details/
  * Node Name: `http://host.docker.internal:8001/opportunities/opportunity_id/details/ ()({lead_name,lead_phone,lead_email})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/opportunities/opportunity_id/follow-up
  * Node Name: `http://host.docker.internal:8001/opportunities/opportunity_id/follow-up ()({next_follow_up_date,follow_up_note})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/opportunities/opportunity_id/follow-up/
  * Node Name: `http://host.docker.internal:8001/opportunities/opportunity_id/follow-up/ ()({next_follow_up_date,follow_up_note})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/opportunities/opportunity_id/link-client
  * Node Name: `http://host.docker.internal:8001/opportunities/opportunity_id/link-client ()({client_id})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/opportunities/opportunity_id/link-client/
  * Node Name: `http://host.docker.internal:8001/opportunities/opportunity_id/link-client/ ()({client_id})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/opportunities/opportunity_id/notes
  * Node Name: `http://host.docker.internal:8001/opportunities/opportunity_id/notes ()({notes})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/opportunities/opportunity_id/notes/
  * Node Name: `http://host.docker.internal:8001/opportunities/opportunity_id/notes/ ()({notes})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/opportunities/opportunity_id/stage
  * Node Name: `http://host.docker.internal:8001/opportunities/opportunity_id/stage ()({stage,next_follow_up_date,lost_reason})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/opportunities/opportunity_id/stage/
  * Node Name: `http://host.docker.internal:8001/opportunities/opportunity_id/stage/ ()({stage,next_follow_up_date,lost_reason})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/payment-entries/entry_id
  * Node Name: `http://host.docker.internal:8001/payment-entries/entry_id ()({milestone_name,amount_received,received_date,gst_tds_amount,notes,milestone_id})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/payment-entries/entry_id/
  * Node Name: `http://host.docker.internal:8001/payment-entries/entry_id/ ()({milestone_name,amount_received,received_date,gst_tds_amount,notes,milestone_id})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/payment-milestones/milestone_id
  * Node Name: `http://host.docker.internal:8001/payment-milestones/milestone_id ()({"name":ZAP,"amount_due":1.2,"due_date":"1970-01-01","notes":"John Doe"})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/payment-milestones/milestone_id/
  * Node Name: `http://host.docker.internal:8001/payment-milestones/milestone_id/ ()({"name":ZAP,"amount_due":1.2,"due_date":"1970-01-01","notes":"John Doe"})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/products/product_id
  * Node Name: `http://host.docker.internal:8001/products/product_id ()({"name":ZAP,"spec":"John Doe","unit":"John Doe","approx_price":1.2,"category":"John Doe","notes":"John Doe"})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/products/product_id/
  * Node Name: `http://host.docker.internal:8001/products/product_id/ ()({"name":ZAP,"spec":"John Doe","unit":"John Doe","approx_price":1.2,"category":"John Doe","notes":"John Doe"})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/calibration
  * Node Name: `http://host.docker.internal:8001/projects/project_id/calibration ()({is_calibration})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/calibration/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/calibration/ ()({is_calibration})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/notes
  * Node Name: `http://host.docker.internal:8001/projects/project_id/notes ()({custom_notes})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/notes/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/notes/ ()({custom_notes})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/sports/selection_id/actual-dimensions
  * Node Name: `http://host.docker.internal:8001/projects/project_id/sports/selection_id/actual-dimensions ()({actual_l_ft,actual_w_ft})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/sports/selection_id/actual-dimensions/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/sports/selection_id/actual-dimensions/ ()({actual_l_ft,actual_w_ft})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/sports/selection_id/build-size
  * Node Name: `http://host.docker.internal:8001/projects/project_id/sports/selection_id/build-size ()({custom_build_l_ft,custom_build_w_ft})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/sports/selection_id/build-size/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/sports/selection_id/build-size/ ()({custom_build_l_ft,custom_build_w_ft})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/technical-bid-checklist/gst
  * Node Name: `http://host.docker.internal:8001/projects/project_id/technical-bid-checklist/gst ()({confirmed})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/technical-bid-checklist/gst/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/technical-bid-checklist/gst/ ()({confirmed})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/cover-note
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/cover-note ()({cover_note})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/cover-note/
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/cover-note/ ()({cover_note})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/rate_item_id
  * Node Name: `http://host.docker.internal:8001/rate-items/rate_item_id ()({category,item_name,spec,unit,hsn_sac,gst_percent,vendor,city_of_quote,labour_category_id,is_commodity_watched})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/rate_item_id/
  * Node Name: `http://host.docker.internal:8001/rate-items/rate_item_id/ ()({category,item_name,spec,unit,hsn_sac,gst_percent,vendor,city_of_quote,labour_category_id,is_commodity_watched})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/scope-items/scope_item_id
  * Node Name: `http://host.docker.internal:8001/scope-items/scope_item_id ()({"display_order":10,"group":"civil","name":ZAP,"is_active":true})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/scope-items/scope_item_id/
  * Node Name: `http://host.docker.internal:8001/scope-items/scope_item_id/ ()({"display_order":10,"group":"civil","name":ZAP,"is_active":true})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/site-surveys/site_survey_id
  * Node Name: `http://host.docker.internal:8001/site-surveys/site_survey_id ()({client_name,site_address,pin_code,contact_name,contact_phone,sports_and_count,available_area_length,available_area_width,area_unit,slope_or_level,soil_observed,water_logging_observed,access_road_width_m,crane_access,power_phase,power_load_kw,water_source,existing_structures_trees,neighbour_constraints,orientation,surveyed_at})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/site-surveys/site_survey_id/
  * Node Name: `http://host.docker.internal:8001/site-surveys/site_survey_id/ ()({client_name,site_address,pin_code,contact_name,contact_phone,sports_and_count,available_area_length,available_area_width,area_unit,slope_or_level,soil_observed,water_logging_observed,access_road_width_m,crane_access,power_phase,power_load_kw,water_source,existing_structures_trees,neighbour_constraints,orientation,surveyed_at})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/sports/sport_id
  * Node Name: `http://host.docker.internal:8001/sports/sport_id ()({"display_order":10,"name":ZAP,"category":"indoor","playing_dims":"John Doe","build_dims":"John Doe","playing_l_ft":1.2,"playing_w_ft":1.2,"build_l_ft":1.2,"build_w_ft":1.2,"min_clear_height_ft":1.2,"governing_body":"John Doe","source_citation":"John Doe","is_active":true})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/sports/sport_id/
  * Node Name: `http://host.docker.internal:8001/sports/sport_id/ ()({"display_order":10,"name":ZAP,"category":"indoor","playing_dims":"John Doe","build_dims":"John Doe","playing_l_ft":1.2,"playing_w_ft":1.2,"build_l_ft":1.2,"build_w_ft":1.2,"min_clear_height_ft":1.2,"governing_body":"John Doe","source_citation":"John Doe","is_active":true})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/users/user_id
  * Node Name: `http://host.docker.internal:8001/users/user_id ()({role,is_active})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/users/user_id/
  * Node Name: `http://host.docker.internal:8001/users/user_id/ ()({role,is_active})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vehicle-classes/vehicle_class_id
  * Node Name: `http://host.docker.internal:8001/vehicle-classes/vehicle_class_id ()({"name":ZAP,"truck_capacity_tonnes":1.2,"rate_per_km":1.2,"is_active":true})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vehicle-classes/vehicle_class_id/
  * Node Name: `http://host.docker.internal:8001/vehicle-classes/vehicle_class_id/ ()({"name":ZAP,"truck_capacity_tonnes":1.2,"rate_per_km":1.2,"is_active":true})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vendors/vendor_id
  * Node Name: `http://host.docker.internal:8001/vendors/vendor_id ()({"name":ZAP,"vendor_code":"John Doe","city":East Romaineburgh,"category":"John Doe","contact_name":"John Doe","phone":9999999999,"email":zaproxy@example.com,"gstin":"John Doe","rcm_applicable":true,"payment_terms":"John Doe","reliability_score":1.2,"whatsapp_opt_in":true,"email_opt_in":true,"consent_date":"1970-01-01","is_active":true})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vendors/vendor_id/
  * Node Name: `http://host.docker.internal:8001/vendors/vendor_id/ ()({"name":ZAP,"vendor_code":"John Doe","city":East Romaineburgh,"category":"John Doe","contact_name":"John Doe","phone":9999999999,"email":zaproxy@example.com,"gstin":"John Doe","rcm_applicable":true,"payment_terms":"John Doe","reliability_score":1.2,"whatsapp_opt_in":true,"email_opt_in":true,"consent_date":"1970-01-01","is_active":true})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/work-orders/work_order_id
  * Node Name: `http://host.docker.internal:8001/work-orders/work_order_id ()({status})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/work-orders/work_order_id/
  * Node Name: `http://host.docker.internal:8001/work-orders/work_order_id/ ()({status})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/accessory-catalog
  * Node Name: `http://host.docker.internal:8001/accessory-catalog ()({sport_id,item_name,unit,quantity_per_court})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/accessory-catalog/
  * Node Name: `http://host.docker.internal:8001/accessory-catalog/ ()({sport_id,item_name,unit,quantity_per_court})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/attachments
  * Node Name: `http://host.docker.internal:8001/attachments ()(multipart:doc_type,doc_id,tag,approval_strength,signatory_name,signatory_designation,file)`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/attachments/
  * Node Name: `http://host.docker.internal:8001/attachments/ ()(multipart:doc_type,doc_id,tag,approval_strength,signatory_name,signatory_designation,file)`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/attachments/attachment_id/supersede
  * Node Name: `http://host.docker.internal:8001/attachments/attachment_id/supersede ()(multipart:tag,approval_strength,signatory_name,signatory_designation,file)`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/attachments/attachment_id/supersede/
  * Node Name: `http://host.docker.internal:8001/attachments/attachment_id/supersede/ ()(multipart:tag,approval_strength,signatory_name,signatory_designation,file)`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/auth/change-password
  * Node Name: `http://host.docker.internal:8001/auth/change-password ()({current_password,new_password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `400`
  * Other Info: ``
* URL: http://host.docker.internal:8001/auth/change-password
  * Node Name: `http://host.docker.internal:8001/auth/change-password ()({current_password,new_password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/auth/change-password/
  * Node Name: `http://host.docker.internal:8001/auth/change-password/ ()({current_password,new_password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/auth/login
  * Node Name: `http://host.docker.internal:8001/auth/login ()(client_id,client_secret,grant_type,password,scope,username)`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/auth/login/
  * Node Name: `http://host.docker.internal:8001/auth/login/ ()(client_id,client_secret,grant_type,password,scope,username)`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients
  * Node Name: `http://host.docker.internal:8001/clients ()({"name":"ZAP","type":"school","contact_name":"John Doe","phone":9999999999,"email":zaproxy@example.com,"city":East Romaineburgh,"billing_address":"John Doe","gstin":"John Doe","pan":"John Doe","payment_terms":"John Doe","whatsapp_opt_in":false,"email_opt_in":true,"consent_date":"1970-01-01","telegram_opt_in":false,"telegram_chat_id":"John Doe","notes":"John Doe"})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/
  * Node Name: `http://host.docker.internal:8001/clients/ ()({"name":"ZAP","type":"school","contact_name":"John Doe","phone":9999999999,"email":zaproxy@example.com,"city":East Romaineburgh,"billing_address":"John Doe","gstin":"John Doe","pan":"John Doe","payment_terms":"John Doe","whatsapp_opt_in":false,"email_opt_in":true,"consent_date":"1970-01-01","telegram_opt_in":false,"telegram_chat_id":"John Doe","notes":"John Doe"})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/client_id/signatories
  * Node Name: `http://host.docker.internal:8001/clients/client_id/signatories ()({"name":"ZAP","designation":"John Doe","email":zaproxy@example.com,"phone":9999999999,"authorization_date":"1970-01-01","authorization_doc_attachment_id":"John Doe","expiry_date":"1970-01-01"})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/clients/client_id/signatories/
  * Node Name: `http://host.docker.internal:8001/clients/client_id/signatories/ ()({"name":"ZAP","designation":"John Doe","email":zaproxy@example.com,"phone":9999999999,"authorization_date":"1970-01-01","authorization_doc_attachment_id":"John Doe","expiry_date":"1970-01-01"})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/company/logo
  * Node Name: `http://host.docker.internal:8001/company/logo ()(multipart:file)`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/company/logo/
  * Node Name: `http://host.docker.internal:8001/company/logo/ ()(multipart:file)`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/construction-sequence/draft/sport_id
  * Node Name: `http://host.docker.internal:8001/construction-sequence/draft/sport_id`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/construction-sequence/draft/sport_id/
  * Node Name: `http://host.docker.internal:8001/construction-sequence/draft/sport_id/`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/accessories
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/accessories ()({project_sport_id,rates:{John Doe},custom_items:[{item_name,unit,quantity,rate}]})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/accessories/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/accessories/ ()({project_sport_id,rates:{John Doe},custom_items:[{item_name,unit,quantity,rate}]})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/athletics
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/athletics ()({project_sport_id,lanes,inner_radius_m,straight_length_m,track_surface_rate_per_sqm,kerb_rate_per_m,drainage_rate_per_m,field_events:[{event_name,rate}]})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/athletics/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/athletics/ ()({project_sport_id,lanes,inner_radius_m,straight_length_m,track_surface_rate_per_sqm,kerb_rate_per_m,drainage_rate_per_m,field_events:[{event_name,rate}]})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/base
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/base ()({project_sport_id,base_type,thickness_in,build_l_ft,build_w_ft,material_rate_per_cum,steel_kg_per_cum,steel_rate_per_kg})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/base/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/base/ ()({project_sport_id,base_type,thickness_in,build_l_ft,build_w_ft,material_rate_per_cum,steel_kg_per_cum,steel_rate_per_kg})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/design-approvals
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/design-approvals ()({car_policy_premium,workmens_comp_premium})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/design-approvals/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/design-approvals/ ()({car_policy_premium,workmens_comp_premium})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/drainage
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/drainage ()({project_sport_id,build_l_ft,build_w_ft,runoff_coefficient,rainfall_intensity_mm_per_hr,high_rainfall,drain_rate_per_m,pipe_rate_per_m,catch_pit_rate_each,subsurface_turf_drainage,subsurface_pipe_rate_per_m})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/drainage/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/drainage/ ()({project_sport_id,build_l_ft,build_w_ft,runoff_coefficient,rainfall_intensity_mm_per_hr,high_rainfall,drain_rate_per_m,pipe_rate_per_m,catch_pit_rate_each,subsurface_turf_drainage,subsurface_pipe_rate_per_m})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/acrylic-pu
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/acrylic-pu ()({project_sport_id,build_l_ft,build_w_ft,surface_type,coats,rate_per_sqft_per_coat})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/acrylic-pu/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/acrylic-pu/ ()({project_sport_id,build_l_ft,build_w_ft,surface_type,coats,rate_per_sqft_per_coat})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/hockey-irrigation
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/hockey-irrigation ()({project_sport_id,cannon_count,cannon_rate_each,pump_rate,tank_rate})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/hockey-irrigation/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/hockey-irrigation/ ()({project_sport_id,cannon_count,cannon_rate_each,pump_rate,tank_rate})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/line-marking
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/line-marking ()({project_sport_id,sets:[{sport_label,style,rate_per_set}]})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/line-marking/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/line-marking/ ()({project_sport_id,sets:[{sport_label,style,rate_per_set}]})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/natural-grass
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/natural-grass ()({project_sport_id,build_l_ft,build_w_ft,topsoil_rate_per_cum,cover_type,cover_rate_per_sqm,sprinkler_spacing_m,sprinkler_rate_each,pump_rate,tank_rate})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/natural-grass/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/natural-grass/ ()({project_sport_id,build_l_ft,build_w_ft,topsoil_rate_per_cum,cover_type,cover_rate_per_sqm,sprinkler_spacing_m,sprinkler_rate_each,pump_rate,tank_rate})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/turf
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/turf ()({project_sport_id,build_l_ft,build_w_ft,pile_height,cut_length_allowed,turf_rate_per_sqm,sand_rate_per_kg,rubber_rate_per_kg,sand_kg_per_sqm,rubber_kg_per_sqm,line_marking_sets,line_marking_rate_per_set})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/turf/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/turf/ ()({project_sport_id,build_l_ft,build_w_ft,pile_height,cut_length_allowed,turf_rate_per_sqm,sand_rate_per_kg,rubber_rate_per_kg,sand_kg_per_sqm,rubber_kg_per_sqm,line_marking_sets,line_marking_rate_per_set})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/wooden
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/wooden ()({project_sport_id,build_l_ft,build_w_ft,hardwood_rate_per_sqft,include_ply,ply_rate_per_sqft,include_battens,battens_rate_per_sqft,include_moisture_barrier,moisture_barrier_rate_per_sqft})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/wooden/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/flooring/wooden/ ()({project_sport_id,build_l_ft,build_w_ft,hardwood_rate_per_sqft,include_ply,ply_rate_per_sqft,include_battens,battens_rate_per_sqft,include_moisture_barrier,moisture_barrier_rate_per_sqft})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/freight-crane
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/freight-crane ()({trips,total_material_tonnes,vehicle_class_id,distance_km,rate_per_km,crane_days,crane_day_rate})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/freight-crane/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/freight-crane/ ()({trips,total_material_tonnes,vehicle_class_id,distance_km,rate_per_km,crane_days,crane_day_rate})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/gym
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/gym ()({project_sport_id,zones:[{zone_name,area_sqft,flooring_rate_per_sqft}],equipment:[{item_name,brand_tier,quantity,rate}],capacity_users_per_hour,electrical_point_rate})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/gym/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/gym/ ()({project_sport_id,zones:[{zone_name,area_sqft,flooring_rate_per_sqft}],equipment:[{item_name,brand_tier,quantity,rate}],capacity_users_per_hour,electrical_point_rate})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/hvac
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/hvac ()({project_sport_id,build_l_ft,build_w_ft,height_ft,climate,ac_rate_per_tr,ducting_rate_per_sqft,occupancy,fresh_air_unit_rate,coverage_percent,acoustic_panel_rate_per_sqm})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/hvac/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/hvac/ ()({project_sport_id,build_l_ft,build_w_ft,height_ft,climate,ac_rate_per_tr,ducting_rate_per_sqft,occupancy,fresh_air_unit_rate,coverage_percent,acoustic_panel_rate_per_sqm})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/lighting
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/lighting ()({project_sport_id,build_l_ft,build_w_ft,lux,lumens_per_fixture,wattage_per_fixture,fixture_rate_each,uses_poles,pole_count,pole_height_m,cable_length_m,cable_rate_per_m,mcb_panel_rate,earthing_rate,lightning_arrestor_rate,tariff_rate_per_kwh,hours_per_day})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/lighting/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/lighting/ ()({project_sport_id,build_l_ft,build_w_ft,lux,lumens_per_fixture,wattage_per_fixture,fixture_rate_each,uses_poles,pole_count,pole_height_m,cable_length_m,cable_rate_per_m,mcb_panel_rate,earthing_rate,lightning_arrestor_rate,tariff_rate_per_kwh,hours_per_day})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/lines
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/lines ()({project_sport_id,rate_item_id,work_package,category,item_name,spec,unit,quantity,rate,source,city_of_quote,labour_category_id,wastage_percent})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/lines/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/lines/ ()({project_sport_id,rate_item_id,work_package,category,item_name,spec,unit,quantity,rate,source,city_of_quote,labour_category_id,wastage_percent})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/play-equipment
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/play-equipment ()({project_sport_id,items:[{item_name,footprint_l_ft,footprint_w_ft,fall_zone_ft,equipment_height_m,equipment_rate,epdm_rate_per_sqm}]})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/play-equipment/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/play-equipment/ ()({project_sport_id,items:[{item_name,footprint_l_ft,footprint_w_ft,fall_zone_ft,equipment_height_m,equipment_rate,epdm_rate_per_sqm}]})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/pool
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/pool ()({project_sport_id,shell:{length_ft,width_ft,shallow_depth_ft,deep_depth_ft,liner_type,shell_thickness_in,steel_kg_per_cum,excavation_rate_per_cum,pcc_rate_per_cum,rcc_rate_per_cum,steel_rate_per_kg,plaster_rate_per_sqm,tile_rate_per_sqm,coping_rate_per_m,frp_shell_rate_per_sqm},filtration:{turnover_hours,pump_rate,sand_filter_rate,pipework_length_m,pipework_rate_per_m,plant_room_area_sqft,plant_room_rate_per_sqft,skimmer_count,skimmer_rate_each,balancing_tank_rate},treatment:{treatment_type,dosing_system...)`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/pool/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/pool/ ()({project_sport_id,shell:{length_ft,width_ft,shallow_depth_ft,deep_depth_ft,liner_type,shell_thickness_in,steel_kg_per_cum,excavation_rate_per_cum,pcc_rate_per_cum,rcc_rate_per_cum,steel_rate_per_kg,plaster_rate_per_sqm,tile_rate_per_sqm,coping_rate_per_m,frp_shell_rate_per_sqm},filtration:{turnover_hours,pump_rate,sand_filter_rate,pipework_length_m,pipework_rate_per_m,plant_room_area_sqft,plant_room_rate_per_sqft,skimmer_count,skimmer_rate_each,balancing_tank_rate},treatment:{treatment_type,dosing_system...)`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/purchase-orders
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/purchase-orders ()({vendor_id,lines:[{cost_sheet_line_id,quantity,rate}],delivery_date,eway_bill_no})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/purchase-orders/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/purchase-orders/ ()({vendor_id,lines:[{cost_sheet_line_id,quantity,rate}],delivery_date,eway_bill_no})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/recompute
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/recompute`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/recompute/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/recompute/`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/reject
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/reject ()({reason_category,note})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/reject/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/reject/ ()({reason_category,note})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/revise
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/revise ()({cost_total})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/revise/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/revise/ ()({cost_total})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/site-prep
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/site-prep ()({project_sport_id,cut_fill_volume_cum,cut_fill_rate_per_cum,rock_breaking_volume_cum,rock_breaking_rate_per_cum,dewatering_days,dewatering_rate_per_day,debris_removal_trips,debris_removal_rate_per_trip,anti_termite_area_sqft,anti_termite_rate_per_sqft})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/site-prep/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/site-prep/ ()({project_sport_id,cut_fill_volume_cum,cut_fill_rate_per_cum,rock_breaking_volume_cum,rock_breaking_rate_per_cum,dewatering_days,dewatering_rate_per_day,debris_removal_trips,debris_removal_rate_per_trip,anti_termite_area_sqft,anti_termite_rate_per_sqft})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/structures
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/structures ()({project_sport_id,structure_type,section,wall_thickness_mm,build_l_ft,build_w_ft,height_ft,column_spacing_ft,foundation_depth_ft,tall_variant,steel_rate_per_kg,netting_grade_id,netting_rate_per_sqm,concrete_rate_per_cum,finish_rate_per_kg,wind_zone,seismic_zone,coastal})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/structures/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/structures/ ()({project_sport_id,structure_type,section,wall_thickness_mm,build_l_ft,build_w_ft,height_ft,column_spacing_ft,foundation_depth_ft,tall_variant,steel_rate_per_kg,netting_grade_id,netting_rate_per_sqm,concrete_rate_per_cum,finish_rate_per_kg,wind_zone,seismic_zone,coastal})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/tender-overheads
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/tender-overheads ()({tender_fee,bg_amount,bank_charge_percent_pa,contract_weeks,dlp_months})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/tender-overheads/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/tender-overheads/ ()({tender_fee,bg_amount,bank_charge_percent_pa,contract_weeks,dlp_months})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/verify
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/verify`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cost-sheets/cost_sheet_id/verify/
  * Node Name: `http://host.docker.internal:8001/cost-sheets/cost_sheet_id/verify/`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cross-sell-addons
  * Node Name: `http://host.docker.internal:8001/cross-sell-addons ()({"name":"ZAP","category":"lighting","description":Zaproxy alias impedit expedita quisquam pariatur exercitationem. Nemo rerum eveniet dolores rem quia dignissimos.,"cost":1.2,"unit":"John Doe","margin_percent":1.2,"all_sports":false})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cross-sell-addons/
  * Node Name: `http://host.docker.internal:8001/cross-sell-addons/ ()({"name":"ZAP","category":"lighting","description":Zaproxy alias impedit expedita quisquam pariatur exercitationem. Nemo rerum eveniet dolores rem quia dignissimos.,"cost":1.2,"unit":"John Doe","margin_percent":1.2,"all_sports":false})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimate-options/option_id/addons
  * Node Name: `http://host.docker.internal:8001/estimate-options/option_id/addons ()({addon_id})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimate-options/option_id/addons/
  * Node Name: `http://host.docker.internal:8001/estimate-options/option_id/addons/ ()({addon_id})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/estimate_id/options
  * Node Name: `http://host.docker.internal:8001/estimates/estimate_id/options ()({project_sport_id,package,cost_for_option})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/estimate_id/options/
  * Node Name: `http://host.docker.internal:8001/estimates/estimate_id/options/ ()({project_sport_id,package,cost_for_option})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/estimate_id/rebase
  * Node Name: `http://host.docker.internal:8001/estimates/estimate_id/rebase`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/estimate_id/rebase/
  * Node Name: `http://host.docker.internal:8001/estimates/estimate_id/rebase/`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/estimate_id/revise
  * Node Name: `http://host.docker.internal:8001/estimates/estimate_id/revise ()({options:[{project_sport_id,package,cost_for_option}],refresh_pricing})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/estimate_id/revise/
  * Node Name: `http://host.docker.internal:8001/estimates/estimate_id/revise/ ()({options:[{project_sport_id,package,cost_for_option}],refresh_pricing})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/estimate_id/send
  * Node Name: `http://host.docker.internal:8001/estimates/estimate_id/send`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/estimates/estimate_id/send/
  * Node Name: `http://host.docker.internal:8001/estimates/estimate_id/send/`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/hubs
  * Node Name: `http://host.docker.internal:8001/hubs ()({name,city,state_code})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/hubs/
  * Node Name: `http://host.docker.internal:8001/hubs/ ()({name,city,state_code})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/integrations/wa-gateway/webhook
  * Node Name: `http://host.docker.internal:8001/integrations/wa-gateway/webhook`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://host.docker.internal:8001/integrations/wa-gateway/webhook/
  * Node Name: `http://host.docker.internal:8001/integrations/wa-gateway/webhook/`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://host.docker.internal:8001/message-templates
  * Node Name: `http://host.docker.internal:8001/message-templates ()({"document_type":"cost_sheet","channel":"email","name":"ZAP","subject":Zaproxy dolore alias impedit expedita quisquam.,"body":"John Doe","language":"en"})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/message-templates/
  * Node Name: `http://host.docker.internal:8001/message-templates/ ()({"document_type":"cost_sheet","channel":"email","name":"ZAP","subject":Zaproxy dolore alias impedit expedita quisquam.,"body":"John Doe","language":"en"})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/messages
  * Node Name: `http://host.docker.internal:8001/messages ()({"doc_type":"cost_sheet","doc_id":"John Doe","channel":"email","recipient":"John Doe","template_key":"John Doe","template_id":"John Doe","subject":Zaproxy dolore alias impedit expedita quisquam.,"body_note":"John Doe","attachment_id":"John Doe","include_document":false})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/messages/
  * Node Name: `http://host.docker.internal:8001/messages/ ()({"doc_type":"cost_sheet","doc_id":"John Doe","channel":"email","recipient":"John Doe","template_key":"John Doe","template_id":"John Doe","subject":Zaproxy dolore alias impedit expedita quisquam.,"body_note":"John Doe","attachment_id":"John Doe","include_document":false})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/messages/draft
  * Node Name: `http://host.docker.internal:8001/messages/draft ()({doc_type,doc_id,channel})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/messages/draft/
  * Node Name: `http://host.docker.internal:8001/messages/draft/ ()({doc_type,doc_id,channel})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/netting-grades
  * Node Name: `http://host.docker.internal:8001/netting-grades ()({key,name,material,twine,mesh,uv_stabilized,typical_use,rate_per_sqm})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/netting-grades/
  * Node Name: `http://host.docker.internal:8001/netting-grades/ ()({key,name,material,twine,mesh,uv_stabilized,typical_use,rate_per_sqm})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/opportunities
  * Node Name: `http://host.docker.internal:8001/opportunities ()({lead_name,lead_phone,lead_email,client_id,next_follow_up_date,notes})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/opportunities/
  * Node Name: `http://host.docker.internal:8001/opportunities/ ()({lead_name,lead_phone,lead_email,client_id,next_follow_up_date,notes})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/overrides
  * Node Name: `http://host.docker.internal:8001/overrides ()({document_type,document_id,setting_key,override_value,reason})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/overrides/
  * Node Name: `http://host.docker.internal:8001/overrides/ ()({document_type,document_id,setting_key,override_value,reason})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/price-requests
  * Node Name: `http://host.docker.internal:8001/price-requests ()({items:[{rate_item_id,spec_override,quantity_band}],vendor_ids:[],channels:[],required_by,requested_validity_days})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/price-requests/
  * Node Name: `http://host.docker.internal:8001/price-requests/ ()({items:[{rate_item_id,spec_override,quantity_band}],vendor_ids:[],channels:[],required_by,requested_validity_days})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/price-requests/price_request_id/close
  * Node Name: `http://host.docker.internal:8001/price-requests/price_request_id/close`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/price-requests/price_request_id/close/
  * Node Name: `http://host.docker.internal:8001/price-requests/price_request_id/close/`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/price-requests/price_request_id/items/item_id/replies
  * Node Name: `http://host.docker.internal:8001/price-requests/price_request_id/items/item_id/replies ()({vendor_id,raw_reply_text,parsed_rate,parsed_unit,parsed_gst_basis,parsed_validity_days,attachment_id})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/price-requests/price_request_id/items/item_id/replies/
  * Node Name: `http://host.docker.internal:8001/price-requests/price_request_id/items/item_id/replies/ ()({vendor_id,raw_reply_text,parsed_rate,parsed_unit,parsed_gst_basis,parsed_validity_days,attachment_id})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/pricing/quote
  * Node Name: `http://host.docker.internal:8001/pricing/quote ()({cost_incl_contingency,client_type,sport_id,discount_type,discount_value,gst_mode})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/pricing/quote/
  * Node Name: `http://host.docker.internal:8001/pricing/quote/ ()({cost_incl_contingency,client_type,sport_id,discount_type,discount_value,gst_mode})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects
  * Node Name: `http://host.docker.internal:8001/projects ()({client_id,project_type,city,site_address,site_state_code,hub_id,distance_km,site_condition,soil_type,building_status,site_access,power_available,water_available,number_of_courts,unit_system,package,safe_bearing_capacity,existing_building_clear_height_ft,quick_setup,is_calibration,opportunity_id})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/
  * Node Name: `http://host.docker.internal:8001/projects/ ()({client_id,project_type,city,site_address,site_state_code,hub_id,distance_km,site_condition,soil_type,building_status,site_access,power_available,water_available,number_of_courts,unit_system,package,safe_bearing_capacity,existing_building_clear_height_ft,quick_setup,is_calibration,opportunity_id})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/cost-sheets
  * Node Name: `http://host.docker.internal:8001/projects/project_id/cost-sheets ()({cost_total})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/cost-sheets/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/cost-sheets/ ()({cost_total})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/estimates
  * Node Name: `http://host.docker.internal:8001/projects/project_id/estimates ()({options:[{project_sport_id,package,cost_for_option}]})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/estimates/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/estimates/ ()({options:[{project_sport_id,package,cost_for_option}]})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/quotations
  * Node Name: `http://host.docker.internal:8001/projects/project_id/quotations ()({estimate_id,included_option_ids:[],discount_type,discount_value,gst_mode})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/quotations/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/quotations/ ()({estimate_id,included_option_ids:[],discount_type,discount_value,gst_mode})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/quotations/fast-track
  * Node Name: `http://host.docker.internal:8001/projects/project_id/quotations/fast-track ()({cost_sheet_id,package,discount_type,discount_value,gst_mode})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/quotations/fast-track/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/quotations/fast-track/ ()({cost_sheet_id,package,discount_type,discount_value,gst_mode})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/scope-items
  * Node Name: `http://host.docker.internal:8001/projects/project_id/scope-items ()({scope_item_id,note})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/scope-items/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/scope-items/ ()({scope_item_id,note})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/site-surveys
  * Node Name: `http://host.docker.internal:8001/projects/project_id/site-surveys ()({client_name,site_address,pin_code,contact_name,contact_phone})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/site-surveys/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/site-surveys/ ()({client_name,site_address,pin_code,contact_name,contact_phone})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/skip-requests
  * Node Name: `http://host.docker.internal:8001/projects/project_id/skip-requests ()({stage_skipped,reason})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/skip-requests/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/skip-requests/ ()({stage_skipped,reason})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/sports
  * Node Name: `http://host.docker.internal:8001/projects/project_id/sports ()({sport_id,building_status,number_of_courts})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/sports/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/sports/ ()({sport_id,building_status,number_of_courts})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/tender-details
  * Node Name: `http://host.docker.internal:8001/projects/project_id/tender-details ()({emd_amount,emd_validity_date,retention_percent,performance_bg_percent,dlp_months,bid_due_date,pre_bid_meeting_date,opening_date})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/tender-details/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/tender-details/ ()({emd_amount,emd_validity_date,retention_percent,performance_bg_percent,dlp_months,bid_due_date,pre_bid_meeting_date,opening_date})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/tender-details/competitor-bids
  * Node Name: `http://host.docker.internal:8001/projects/project_id/tender-details/competitor-bids ()({bidder_name,amount})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/projects/project_id/tender-details/competitor-bids/
  * Node Name: `http://host.docker.internal:8001/projects/project_id/tender-details/competitor-bids/ ()({bidder_name,amount})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/purchase-orders/po_id/cancel
  * Node Name: `http://host.docker.internal:8001/purchase-orders/po_id/cancel`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/purchase-orders/po_id/cancel/
  * Node Name: `http://host.docker.internal:8001/purchase-orders/po_id/cancel/`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/purchase-orders/po_id/issue
  * Node Name: `http://host.docker.internal:8001/purchase-orders/po_id/issue`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/purchase-orders/po_id/issue/
  * Node Name: `http://host.docker.internal:8001/purchase-orders/po_id/issue/`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/purchase-orders/po_id/receive
  * Node Name: `http://host.docker.internal:8001/purchase-orders/po_id/receive ()({lines:[{line_id,received_qty,expected_received_qty}]})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/purchase-orders/po_id/receive/
  * Node Name: `http://host.docker.internal:8001/purchase-orders/po_id/receive/ ()({lines:[{line_id,received_qty,expected_received_qty}]})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/draft-cover-note
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/draft-cover-note`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/draft-cover-note/
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/draft-cover-note/`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/mark-lost
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/mark-lost ()({reason,waive_evidence_reason})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/mark-lost/
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/mark-lost/ ()({reason,waive_evidence_reason})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/mark-won
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/mark-won ()({reason,waive_evidence_reason})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/mark-won/
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/mark-won/ ()({reason,waive_evidence_reason})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/preview-pdf
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/preview-pdf ()({terms:[],warranty_table:[]})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/preview-pdf/
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/preview-pdf/ ()({terms:[],warranty_table:[]})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/reject
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/reject ()({reason_category,note})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/reject/
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/reject/ ()({reason_category,note})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/release
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/release`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/release/
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/release/`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/revise
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/revise ()({included_option_ids:[],discount_type,discount_value,gst_mode,refresh_pricing})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/revise/
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/revise/ ()({included_option_ids:[],discount_type,discount_value,gst_mode,refresh_pricing})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/send
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/send`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/send/
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/send/`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/work-order
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/work-order`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/quotations/quotation_id/work-order/
  * Node Name: `http://host.docker.internal:8001/quotations/quotation_id/work-order/`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items
  * Node Name: `http://host.docker.internal:8001/rate-items ()({category,item_name,spec,unit,hsn_sac,rate,gst_percent,vendor,city_of_quote,labour_category_id,is_commodity_watched,vendor_id,project_id,reason})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/
  * Node Name: `http://host.docker.internal:8001/rate-items/ ()({category,item_name,spec,unit,hsn_sac,rate,gst_percent,vendor,city_of_quote,labour_category_id,is_commodity_watched,vendor_id,project_id,reason})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/bulk-mark
  * Node Name: `http://host.docker.internal:8001/rate-items/bulk-mark ()({source,category})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/bulk-mark/
  * Node Name: `http://host.docker.internal:8001/rate-items/bulk-mark/ ()({source,category})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/bulk-rate-update
  * Node Name: `http://host.docker.internal:8001/rate-items/bulk-rate-update ()({category,percent_change,reason,effective_from})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/bulk-rate-update/
  * Node Name: `http://host.docker.internal:8001/rate-items/bulk-rate-update/ ()({category,percent_change,reason,effective_from})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/import
  * Node Name: `http://host.docker.internal:8001/rate-items/import ()(multipart:file)`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/import/
  * Node Name: `http://host.docker.internal:8001/rate-items/import/ ()(multipart:file)`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/rate_item_id/confirm
  * Node Name: `http://host.docker.internal:8001/rate-items/rate_item_id/confirm`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/rate_item_id/confirm/
  * Node Name: `http://host.docker.internal:8001/rate-items/rate_item_id/confirm/`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/rate_item_id/rate
  * Node Name: `http://host.docker.internal:8001/rate-items/rate_item_id/rate ()({rate,reason,vendor_id,project_id,effective_from})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/rate_item_id/rate/
  * Node Name: `http://host.docker.internal:8001/rate-items/rate_item_id/rate/ ()({rate,reason,vendor_id,project_id,effective_from})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/rate_item_id/sync-draft-lines
  * Node Name: `http://host.docker.internal:8001/rate-items/rate_item_id/sync-draft-lines`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/rate-items/rate_item_id/sync-draft-lines/
  * Node Name: `http://host.docker.internal:8001/rate-items/rate_item_id/sync-draft-lines/`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/reports/generate
  * Node Name: `http://host.docker.internal:8001/reports/generate ()({report_type,period_from,period_to})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/reports/report_id/release
  * Node Name: `http://host.docker.internal:8001/reports/report_id/release`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/reports/report_id/release/
  * Node Name: `http://host.docker.internal:8001/reports/report_id/release/`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/reports/report_id/summary
  * Node Name: `http://host.docker.internal:8001/reports/report_id/summary`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/reports/report_id/summary/
  * Node Name: `http://host.docker.internal:8001/reports/report_id/summary/`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/scope-items
  * Node Name: `http://host.docker.internal:8001/scope-items ()({key,display_order,group,name})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/scope-items/
  * Node Name: `http://host.docker.internal:8001/scope-items/ ()({key,display_order,group,name})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/settings
  * Node Name: `http://host.docker.internal:8001/settings ()({key,scope,scope_value,value,unit,effective_from,reason})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/settings/
  * Node Name: `http://host.docker.internal:8001/settings/ ()({key,scope,scope_value,value,unit,effective_from,reason})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/settings/bulk-update
  * Node Name: `http://host.docker.internal:8001/settings/bulk-update ()({key_prefix,percent_change,effective_from,reason})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/settings/bulk-update/
  * Node Name: `http://host.docker.internal:8001/settings/bulk-update/ ()({key_prefix,percent_change,effective_from,reason})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/settings/import
  * Node Name: `http://host.docker.internal:8001/settings/import ()(multipart:file)`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/settings/import/
  * Node Name: `http://host.docker.internal:8001/settings/import/ ()(multipart:file)`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/site-surveys/site_survey_id/complete
  * Node Name: `http://host.docker.internal:8001/site-surveys/site_survey_id/complete`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/site-surveys/site_survey_id/complete/
  * Node Name: `http://host.docker.internal:8001/site-surveys/site_survey_id/complete/`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/skip-requests/skip_request_id/approve
  * Node Name: `http://host.docker.internal:8001/skip-requests/skip_request_id/approve ()({cost_total})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/skip-requests/skip_request_id/approve/
  * Node Name: `http://host.docker.internal:8001/skip-requests/skip_request_id/approve/ ()({cost_total})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/skip-requests/skip_request_id/reject
  * Node Name: `http://host.docker.internal:8001/skip-requests/skip_request_id/reject ()({reason})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/skip-requests/skip_request_id/reject/
  * Node Name: `http://host.docker.internal:8001/skip-requests/skip_request_id/reject/ ()({reason})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/sports
  * Node Name: `http://host.docker.internal:8001/sports ()({key,display_order,name,category,playing_dims,build_dims,playing_l_ft,playing_w_ft,build_l_ft,build_w_ft,min_clear_height_ft,governing_body,source_citation})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/sports/
  * Node Name: `http://host.docker.internal:8001/sports/ ()({key,display_order,name,category,playing_dims,build_dims,playing_l_ft,playing_w_ft,build_l_ft,build_w_ft,min_clear_height_ft,governing_body,source_citation})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/tender/net-receivable
  * Node Name: `http://host.docker.internal:8001/tender/net-receivable ()({quotation_total,retention_percent,gst_tds_percent})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/tender/net-receivable/
  * Node Name: `http://host.docker.internal:8001/tender/net-receivable/ ()({quotation_total,retention_percent,gst_tds_percent})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/tender/performance-bg-cost
  * Node Name: `http://host.docker.internal:8001/tender/performance-bg-cost ()({bg_amount,bank_charge_percent_pa,contract_weeks,dlp_months})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/tender/performance-bg-cost/
  * Node Name: `http://host.docker.internal:8001/tender/performance-bg-cost/ ()({bg_amount,bank_charge_percent_pa,contract_weeks,dlp_months})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/users
  * Node Name: `http://host.docker.internal:8001/users ()({name,email,role,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/users/
  * Node Name: `http://host.docker.internal:8001/users/ ()({name,email,role,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/users/user_id/reset-password
  * Node Name: `http://host.docker.internal:8001/users/user_id/reset-password ()({new_password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/users/user_id/reset-password/
  * Node Name: `http://host.docker.internal:8001/users/user_id/reset-password/ ()({new_password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vehicle-classes
  * Node Name: `http://host.docker.internal:8001/vehicle-classes ()({key,name,truck_capacity_tonnes,rate_per_km})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vehicle-classes/
  * Node Name: `http://host.docker.internal:8001/vehicle-classes/ ()({key,name,truck_capacity_tonnes,rate_per_km})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vendor-replies/reply_id/use
  * Node Name: `http://host.docker.internal:8001/vendor-replies/reply_id/use ()({apply_to,cost_sheet_line_id,confirmed_ex_gst})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vendor-replies/reply_id/use/
  * Node Name: `http://host.docker.internal:8001/vendor-replies/reply_id/use/ ()({apply_to,cost_sheet_line_id,confirmed_ex_gst})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vendors
  * Node Name: `http://host.docker.internal:8001/vendors ()({"name":"ZAP","vendor_code":"John Doe","city":East Romaineburgh,"category":"John Doe","contact_name":"John Doe","phone":9999999999,"email":zaproxy@example.com,"gstin":"John Doe","rcm_applicable":false,"payment_terms":"John Doe","reliability_score":1.2,"whatsapp_opt_in":false,"email_opt_in":true,"consent_date":"1970-01-01"})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vendors/
  * Node Name: `http://host.docker.internal:8001/vendors/ ()({"name":"ZAP","vendor_code":"John Doe","city":East Romaineburgh,"category":"John Doe","contact_name":"John Doe","phone":9999999999,"email":zaproxy@example.com,"gstin":"John Doe","rcm_applicable":false,"payment_terms":"John Doe","reliability_score":1.2,"whatsapp_opt_in":false,"email_opt_in":true,"consent_date":"1970-01-01"})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vendors/vendor_id/products
  * Node Name: `http://host.docker.internal:8001/vendors/vendor_id/products ()({name,spec,unit,approx_price,category,notes})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/vendors/vendor_id/products/
  * Node Name: `http://host.docker.internal:8001/vendors/vendor_id/products/ ()({name,spec,unit,approx_price,category,notes})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/work-orders/work_order_id/payment-entries
  * Node Name: `http://host.docker.internal:8001/work-orders/work_order_id/payment-entries ()({milestone_name,amount_received,received_date,gst_tds_amount,notes,milestone_id})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/work-orders/work_order_id/payment-entries/
  * Node Name: `http://host.docker.internal:8001/work-orders/work_order_id/payment-entries/ ()({milestone_name,amount_received,received_date,gst_tds_amount,notes,milestone_id})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/work-orders/work_order_id/payment-milestones
  * Node Name: `http://host.docker.internal:8001/work-orders/work_order_id/payment-milestones ()({name,amount_due,due_date,notes})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/work-orders/work_order_id/payment-milestones/
  * Node Name: `http://host.docker.internal:8001/work-orders/work_order_id/payment-milestones/ ()({name,amount_due,due_date,notes})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/construction-sequence/sport_id
  * Node Name: `http://host.docker.internal:8001/construction-sequence/sport_id ()({steps:[{phase,description}]})`
  * Method: `PUT`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/construction-sequence/sport_id/
  * Node Name: `http://host.docker.internal:8001/construction-sequence/sport_id/ ()({steps:[{phase,description}]})`
  * Method: `PUT`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cross-sell-addons/addon_id/sports
  * Node Name: `http://host.docker.internal:8001/cross-sell-addons/addon_id/sports ()({sport_ids:[]})`
  * Method: `PUT`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cross-sell-addons/addon_id/sports/
  * Node Name: `http://host.docker.internal:8001/cross-sell-addons/addon_id/sports/ ()({sport_ids:[]})`
  * Method: `PUT`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/flooring-guides/sport_id
  * Node Name: `http://host.docker.internal:8001/flooring-guides/sport_id ()({primary_spec,secondary_spec,budget_spec,rationale})`
  * Method: `PUT`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/flooring-guides/sport_id/
  * Node Name: `http://host.docker.internal:8001/flooring-guides/sport_id/ ()({primary_spec,secondary_spec,budget_spec,rationale})`
  * Method: `PUT`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/lighting-standards/lux/category
  * Node Name: `http://host.docker.internal:8001/lighting-standards/lux/category ()({lux_practice,lux_match,lux_tournament})`
  * Method: `PUT`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/lighting-standards/lux/category/
  * Node Name: `http://host.docker.internal:8001/lighting-standards/lux/category/ ()({lux_practice,lux_match,lux_tournament})`
  * Method: `PUT`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/lighting-standards/pole-counts/sport_id
  * Node Name: `http://host.docker.internal:8001/lighting-standards/pole-counts/sport_id ()({pole_count})`
  * Method: `PUT`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/lighting-standards/pole-counts/sport_id/
  * Node Name: `http://host.docker.internal:8001/lighting-standards/pole-counts/sport_id/ ()({pole_count})`
  * Method: `PUT`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/package-contents/sport_id/budget
  * Node Name: `http://host.docker.internal:8001/package-contents/sport_id/budget ()({flooring_description,structure_description,lighting_description,scope_description,warranty_years})`
  * Method: `PUT`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/package-contents/sport_id/budget/
  * Node Name: `http://host.docker.internal:8001/package-contents/sport_id/budget/ ()({flooring_description,structure_description,lighting_description,scope_description,warranty_years})`
  * Method: `PUT`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/sport-margin-policies/sport_id
  * Node Name: `http://host.docker.internal:8001/sport-margin-policies/sport_id ()({floor_margin_percent})`
  * Method: `PUT`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``
* URL: http://host.docker.internal:8001/sport-margin-policies/sport_id/
  * Node Name: `http://host.docker.internal:8001/sport-margin-policies/sport_id/ ()({floor_margin_percent})`
  * Method: `PUT`
  * Parameter: ``
  * Attack: ``
  * Evidence: `403`
  * Other Info: ``


Instances: 676

### Solution



### Reference



#### CWE Id: [ 388 ](https://cwe.mitre.org/data/definitions/388.html)


#### WASC Id: 20

#### Source ID: 4

### [ Authentication Request Identified ](https://www.zaproxy.org/docs/alerts/10111/)



##### Informational (High)

### Description

The given request has been identified as an authentication request. The 'Other Info' field contains a set of key=value lines which identify any relevant fields. If the request is in a context which has an Authentication Method set to "Auto-Detect" then this rule will change the authentication to match the request identified.

* URL: http://host.docker.internal:8001/users
  * Node Name: `http://host.docker.internal:8001/users ()({name,email,role,password})`
  * Method: `POST`
  * Parameter: `email`
  * Attack: ``
  * Evidence: `password`
  * Other Info: `userParam=email
userValue=zaproxy@example.com
passwordParam=password`
* URL: http://host.docker.internal:8001/auth/login
  * Node Name: `http://host.docker.internal:8001/auth/login ()(client_id,client_secret,grant_type,password,scope,username)`
  * Method: `POST`
  * Parameter: `username`
  * Attack: ``
  * Evidence: `password`
  * Other Info: `userParam=username
userValue=username
passwordParam=password`


Instances: 2

### Solution

This is an informational alert rather than a vulnerability and so there is nothing to fix.

### Reference


* [ https://www.zaproxy.org/docs/desktop/addons/authentication-helper/auth-req-id/ ](https://www.zaproxy.org/docs/desktop/addons/authentication-helper/auth-req-id/)



#### Source ID: 3

### [ Non-Storable Content ](https://www.zaproxy.org/docs/alerts/10049/)



##### Informational (Medium)

### Description

The response contents are not storable by caching components such as proxy servers. If the response does not contain sensitive, personal or user-specific information, it may benefit from being stored and cached, to improve performance.

* URL: http://host.docker.internal:8001/auth/me
  * Node Name: `http://host.docker.internal:8001/auth/me`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `authorization:`
  * Other Info: ``
* URL: http://host.docker.internal:8001/users
  * Node Name: `http://host.docker.internal:8001/users`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `authorization:`
  * Other Info: ``
* URL: http://host.docker.internal:8001/users/user_id
  * Node Name: `http://host.docker.internal:8001/users/user_id ()({role,is_active})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `PATCH `
  * Other Info: ``
* URL: http://host.docker.internal:8001/auth/change-password
  * Node Name: `http://host.docker.internal:8001/auth/change-password ()({current_password,new_password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `authorization:`
  * Other Info: ``
* URL: http://host.docker.internal:8001/users
  * Node Name: `http://host.docker.internal:8001/users ()({name,email,role,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `authorization:`
  * Other Info: ``

Instances: Systemic


### Solution

The content may be marked as storable by ensuring that the following conditions are satisfied:
The request method must be understood by the cache and defined as being cacheable ("GET", "HEAD", and "POST" are currently defined as cacheable)
The response status code must be understood by the cache (one of the 1XX, 2XX, 3XX, 4XX, or 5XX response classes are generally understood)
The "no-store" cache directive must not appear in the request or response header fields
For caching by "shared" caches such as "proxy" caches, the "private" response directive must not appear in the response
For caching by "shared" caches such as "proxy" caches, the "Authorization" header field must not appear in the request, unless the response explicitly allows it (using one of the "must-revalidate", "public", or "s-maxage" Cache-Control response directives)
In addition to the conditions above, at least one of the following conditions must also be satisfied by the response:
It must contain an "Expires" header field
It must contain a "max-age" response directive
For "shared" caches such as "proxy" caches, it must contain a "s-maxage" response directive
It must contain a "Cache Control Extension" that allows it to be cached
It must have a status code that is defined as cacheable by default (200, 203, 204, 206, 300, 301, 404, 405, 410, 414, 501).

### Reference


* [ https://datatracker.ietf.org/doc/html/rfc7234 ](https://datatracker.ietf.org/doc/html/rfc7234)
* [ https://datatracker.ietf.org/doc/html/rfc7231 ](https://datatracker.ietf.org/doc/html/rfc7231)
* [ https://www.w3.org/Protocols/rfc2616/rfc2616-sec13.html ](https://www.w3.org/Protocols/rfc2616/rfc2616-sec13.html)


#### CWE Id: [ 524 ](https://cwe.mitre.org/data/definitions/524.html)


#### WASC Id: 13

#### Source ID: 3


