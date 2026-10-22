# Demand forecasting

> Source : Wikipédia (en), « Demand forecasting », révision 1375725813 : https://en.wikipedia.org/wiki/Demand_forecasting?oldid=1375725813
> Licence : CC BY-SA 4.0 (attribution : contributeurs de Wikipédia). Texte brut converti, sections de références retirées.

Demand forecasting, also known as demand planning and sales forecasting (DP&SF), involves the prediction of the quantity of goods and services that will be demanded by consumers or business customers at a future point in time, conditional on a specified forecast horizon and information set. More specifically, the methods of demand forecasting entail using predictive analytics to estimate customer demand in consideration of key economic conditions. This is an important tool in optimizing business profitability through efficient supply chain management. Demand forecasting methods are divided into two major categories, qualitative and quantitative methods:

Qualitative methods are based on expert opinion and information gathered from the field. This method is mostly used in situations when there is minimal data available for analysis, such as when a business or product has recently been introduced to the market.
Quantitative methods use available data and analytical tools in order to produce predictions.
Demand forecasting may be used in resource allocation, inventory management, assessing future capacity requirements, or making decisions on whether to enter a new market.
Customer demand planning (CDP) is a business planning process that allows sales teams to develop demand forecasts.

## Importance of demand forecasting for businesses
Demand forecasting plays an important role for businesses in different industries, particularly with regard to mitigating the risks associated with particular business activities. However, demand forecasting is known to be a challenging task for businesses due to the intricacies of analysis, specifically quantitative analysis. Nevertheless, understanding customer needs is an indispensable part of any industry in order for business activities to be implemented efficiently and more appropriately respond to market needs. If businesses are able to forecast demand effectively, several benefits can be accrued. These include, but are not limited to, waste reduction, optimized allocation of resources, and potentially large increases in sales and revenue.
Some of the reasons why businesses require demand forecasting include:

Meeting goals - Most successful organisations will have pre-determined growth trajectories and long-term plans to ensure the business is operating at an ideal output. By having an understanding of future demand markets, businesses can be proactive in ensuring that goals will be met in this business environment.
Business decisions - In reference to meeting goals, by having a thorough understanding of future industry demand, management and key board members can make strategic business decisions that encourage higher profitability and growth. These decisions are generally associated with the concepts of capacity, market targeting, raw material acquisition and understanding vendor contract direction.
Growth - By having an accurate understanding of future forecasts, companies can gauge the need for expansion within a timeframe that allows them to do so cost effectively.
Human capital management -  If there is a rapid demand increase in an industry but a business does not have enough employees to satisfy the sales orders, consumer loyalty may be adversely affected as customers are forced to purchase from competitors.
Financial planning - It is crucial to understand demand forecasts in order to efficiently budget for future operations in terms of factors such as cash flow, inventory accounting and general operational costs. The use of an accurate demand forecasting model can result in significant decreases in operational costs for businesses, since less safety stock is required to be held.

## Methods for forecasting demand
There are various statistical and econometric analyses used for forecasting demand. Forecasting demand can be broken down into seven stage process, the seven stages are described as:

### Stage 1: statement of a theory or hypothesis
The first step to forecast demand is to determine a set of objectives or information to derive different business strategies. These objectives are based on a set of hypotheses that usually come from a mixture of economic theory or previous empirical studies. For example, a manager may wish to find what the optimal price and production amount would be for a new product, based on how demand elasticity affected past company sales.

### Stage 2: model specification
There are many different econometric models which differ depending on the analysis that managers wish to perform. The type of model that is chosen to forecast demand depends on many different aspects such as the type of data obtained or the number of observations, etc. In this stage it is important to define the type of variables that will be used to forecast demand. Regression analysis is the main statistical method for forecasting. There are many different types of regression analysis, but fundamentally they provide an analysis of how one or multiple variables affect the dependent variable being measured. An example of a model for forecasting demand is M. Roodman's (1986) demand forecasting regression model for measuring the seasonality effects on a data point being measured. The model was based on a linear regression model, and is used to measure linear trends based on seasonal cycles and their effects on demand i.e. the seasonal demand for a product based on sales in summer and winter.
The linear regression model is described as: $Y_{i}=\beta _{0}+\beta _{1}X_{i}+e$ Where $Y_{i}$ is the dependent variable, $\beta _{0}$ is the intercept, $\beta _{1}$ is the slope coefficient, $X_{i}$ is the independent variable and e is the error term.
M. Roodman's demand forecasting model is based on linear regression and is described as: $\lambda _{q}=\{t\mid t=1,\dots ,n{\text{ and }}t{\bmod {Q}}=q\}\qquad q=1,\dots ,Q$ λ $\lambda _{q}$ is defined as the set of all t - indices for quarter q. The process that generates the data for all periods t that fall in quarter q is given by: $Y_{t}=(\beta +\tau \times t)\times \sigma _{q}+e$ Y $Y_{t}$ = the datum for period
β = base demand at the beginning of the time series horizon
τ = the linear trend per quarter $\sigma _{q}$ = the multiplicative seasonal factor for the quarter
e = a disturbance term

### Stage 3: data collection
Once the type of model is specified in stage 2, the data and the method of collecting data must be specified. The model must be specified first in order to determine the variables which need to be collected. Conversely, when deciding on the desired forecasting model, the available data or methods to collect data need to be considered in order to formulate the correct model. Gathering Time series data and cross-sectional data are the different collection methods that may be used. Time series data are based on historical observations taken sequentially in time. These observations are used to derive relevant statistics, characteristics, and insight from the data. The data points that may be collected using time series data may be sales, prices, manufacturing costs, and their corresponding time intervals i.e., weekly, monthly, quarterly, annually, or any other regular interval. Cross-sectional data refers to data collected on a single entity at different periods of time. Cross-sectional data used in demand forecasting usually depicts a data point gathered from an individual, firm, industry, or area. For example, sales for Firm A during quarter 1. This type of data encapsulates a variety of data points which resulted in the final data point. The subset of data points may not be observable or feasible to determine but can be a practical method for adding precision to the demand forecast model. The source for the data can be found via the firm's records, commercial or private agencies, or official sources.

### Stage 4: estimation of parameters
Once the model and data are obtained then the values can be computed to determine the effects the independent variables have on the dependent variable in focus. Using the linear regression model as an example of estimating parameters, the following steps are taken:
Linear regression formula: $Y_{i}=\beta _{0}+\beta _{1}X_{i}+e$ The first step is to find the line that minimizes the sum of the squares of the difference between the observed values of the dependent variable and the fitted values from the line. This is expressed as ${\hat {Y}}_{i}=\beta _{0}+\beta _{1}{X_{i}}$ which minimizes $\Sigma (Y_{i}-{\hat {Y_{i}}})^{2}$ and ${\hat {Y_{i}}}=\beta _{0}$ ,  the fitted value from the regression line. $\beta _{0}$ and $\beta _{1}$ also need to be represented to find the intercept and slope of the line. The method of determining $\beta _{0}$ and $\beta _{1}$ is to use partial differentiation with respect to both $\beta _{0}$ and $\beta _{1}$ by setting both expressions equal to zero and solving them simultaneously. The method for omitting these variables is described below: ${\begin{aligned}\beta _{1}&={\frac {n\Sigma XY-\Sigma X\Sigma y}{n\Sigma X^{2}-(\Sigma X)^{2}}}\\\beta _{0}&={\frac {\Sigma Y}{n}}-{\frac {\beta _{1}\Sigma X}{n}}\end{aligned}}$ === Stage 5: checking the accuracy of the model ===
Calculating demand forecast accuracy is the process of determining the accuracy of forecasts made regarding customer demand for a product. Understanding and predicting customer demand is vital to manufacturers and distributors to avoid stock-outs and to maintain adequate inventory levels.  While forecasts are never perfect, they are necessary to prepare for actual demand. In order to maintain an optimized inventory and effective supply chain, accurate demand forecasts are imperative.

#### Calculating the accuracy of supply chain forecasts
Forecast accuracy in the supply chain is typically measured using the Mean Absolute Percent Error or MAPE. Statistically, MAPE is defined as the average of percentage errors.
Most practitioners, however, define and use the MAPE as the Mean Absolute Deviation divided by Average Sales, which is just a volume-weighted MAPE, also referred to as the MAD/Mean ratio. This is the same as dividing the sum of the absolute deviations by the total sales of all products. This calculation ${\frac {\sum {|A-F|}}{\sum {A}}}$ , where A is the actual value and F the forecast, is also known as WAPE, or the Weighted Absolute Percent Error.
Another interesting option is the weighted ${\text{MAPE}}={\frac {\sum (w\cdot |A-F|)}{\sum (w\cdot A)}}$ . The advantage of this measure is that can weight errors. The only problem is that for seasonal products you will create an undefined result when sales = 0 and that is not symmetrical. This means that you can be much more inaccurate if sales are higher than if they are lower than the forecast. So sMAPE also known as symmetric Mean Absolute Percentage Error, is used to correct this.
Finally, for intermittent demand patterns, none of the above are particularly useful. In this situation, a business may consider MASE (Mean Absolute Scaled Error) as a key performance indicator to use. However, the use of this calculation is challenging as it is not as intuitive as the above-mentioned. Another metric to consider, especially when there are intermittent or lumpy demand patterns at hand, is SPEC (Stock-keeping-oriented Prediction Error Costs). The idea behind this metric is to compare predicted demand and actual demand by computing theoretical incurred costs over the forecast horizon. It assumes, that predicted demand higher than actual demand results in stock-keeping costs, whereas predicted demand lower than actual demand results in opportunity costs. SPEC takes into account temporal shifts (prediction before or after actual demand) or cost-related aspects and allows comparisons between demand forecasts based on business aspects as well.

#### Calculating forecast error
The forecast error needs to be calculated using actual sales as a base. There are several forms of forecast error calculation methods used, namely Mean Percent Error, Root Mean Squared Error, Tracking Signal and Forecast Bias.

### Financial cost of forecast error
While statistical metrics such as MAPE and MSE measure the magnitude of error, they typically treat over-forecasts and under-forecasts symmetrically. However, in supply chain and financial contexts, the cost of error is often asymmetric. The financial impact of carrying excess inventory (holding costs, obsolescence) rarely equals the financial impact of a stock-out (lost margin, expedited freight, loss of customer goodwill).
Research into Enterprise Resource Planning (ERP) environments has shown that standard forecasting modules often fail to account for these asymmetries, leading to sub-optimal inventory performance despite statistical accuracy.
The Cost of Forecast Error (CFE) is a metric designed to explicitly quantify this financial impact. It applies specific cost coefficients to the error direction: ${\text{CFE}}=(C_{under}\times {\text{Error}}_{under})+(C_{over}\times {\text{Error}}_{over})$ Where: $C_{under}$ is the cost per unit of under-forecasting (e.g., lost gross margin). $C_{over}$ is the cost per unit of over-forecasting (e.g., inventory holding cost).
By optimizing for minimum CFE rather than minimum statistical error, organizations can account for the "Symmetry Trap"—a situation where a statistically accurate forecast leads to sub-optimal financial outcomes.

### Stage 6: hypothesis testing
Once the model has been determined, the model is used to test the theory or hypothesis stated in the first stage. The results should describe what is trying to be achieved and determine if the theory or hypothesis is true or false. In relation to the example provided in the first stage, the model should show the relationship between demand elasticity of the market and the correlation it has to past company sales. This should enable managers to make informed decisions regarding the optimal price and production levels for the new product.

### Stage 7: forecasting
The final step is to then forecast demand based on the data set and model created. In order to forecast demand, estimations of a chosen variable are used to determine the effects it has on demand. Regarding the estimation of the chosen variable, a regression model can be used or both qualitative and quantitative assessments can be implemented. Examples of qualitative and quantitative assessments are:

#### Qualitative assessment
Unaided judgment
Marketing research
Delphi technique
Game theory
Judgmental bootstrapping
Simulated interaction
Intentions and expectations survey
jury of executive method

#### Quantitative assessment
Discrete event simulation
Extrapolation
Group method of data handling (GMDH)
Reference class forecasting
Quantitative analogies
Rule-based forecasting
Diffusion of innovation
Neural networks
Data mining
Conjoint analysis
Causal models
Segmentation
Exponential smoothing models
Box–Jenkins models
Hybrid models

#### Others
Others include:

### Software platforms and applications
In practice, demand forecasting methods are increasingly implemented through software platforms that apply machine learning to historical sales data and external factors.
