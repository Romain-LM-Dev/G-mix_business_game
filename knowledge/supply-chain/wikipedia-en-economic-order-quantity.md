# Economic order quantity

> Source : Wikipédia (en), « Economic order quantity », révision 1371190686 : https://en.wikipedia.org/wiki/Economic_order_quantity?oldid=1371190686
> Licence : CC BY-SA 4.0 (attribution : contributeurs de Wikipédia). Texte brut converti, sections de références retirées.

Economic order quantity (EOQ), also known as financial purchase quantity or economic buying quantity, is the order quantity that minimizes the total holding costs and ordering costs in inventory management. It is one of the oldest classical production scheduling models. The model was developed by Ford W. Harris in 1913, but the consultant R. H. Wilson applied it extensively, and he and K. Andler are given credit for their in-depth analysis.

## Overview
The EOQ indicates the optimal number of units to order to minimize the total cost associated with the purchase, delivery, and storage of a product.
EOQ applies only when demand for a product is constant over a period of time (such as a year) and each new order is delivered in full when inventory reaches zero. There is a fixed cost for each order placed, regardless of the quantity of items ordered; an order is assumed to contain only one type of inventory item. There is also a cost for each unit held in storage, commonly known as holding cost, sometimes expressed as a percentage of the purchase cost of the item. Although the EOQ formulation is straightforward, factors such as transportation rates and quantity discounts factor into its real-world application.
The required parameters to the solution are the total demand for the year, the purchase cost for each item, the fixed cost to place the order for a single item and the storage cost for each item per year. Note that the number of times an order is placed will also affect the total cost, though this number can be determined from the other parameters.

=== Variables === $T$ = total annual inventory cost $P$ = purchase unit price, unit production cost $Q$ = order quantity $Q^{*}$ = optimal order quantity $D$ = annual demand quantity $K$ = fixed cost per order, setup cost (not per unit, typically cost of ordering and shipping and handling. This is not the cost of goods) $h$ = annual holding cost per unit, also known as carrying cost or storage cost (capital cost, warehouse space, refrigeration, insurance, opportunity cost (price x interest),  etc. usually not related to the unit production cost)

### Total cost function and derivation of EOQ formula
The single-item EOQ formula finds the minimum point of the following cost function:
Total Cost = purchase cost or production cost + ordering cost + holding cost
Where:

Purchase cost: This is the variable cost of goods: purchase unit price × annual demand quantity. This is $P\times D$ .
Ordering cost: This is the cost of placing orders: each order has a fixed cost $K$ , and we need to order $D/Q$ times per year. This is $KD/Q$ Holding cost: the average quantity in stock (between fully replenished and empty) is $Q/2$ , so this cost is $hQ/2$ T $T=PD+K{\frac {D}{Q}}+h{\frac {Q}{2}}$ .
To determine the minimum point of the total cost curve, calculate the derivative of the total cost with respect to Q (assume all other variables are constant) and set it equal to 0: ${0}=-{\frac {DK}{Q^{2}}}+{\frac {h}{2}}$ Solving for Q gives Q* (the optimal order quantity): $Q^{*2}={\frac {2DK}{h}}$ Therefore:

Q* is independent of P; it is a function of only K, D, h.
The optimal value Q* may also be found by recognizing that $T={\frac {DK}{Q}}+{\frac {hQ}{2}}+PD={\frac {h}{2Q}}(Q-{\sqrt {2DK/h}})^{2}+{\sqrt {2hDK}}+PD,$ where the non-negative quadratic term disappears for 
  
    
      
        Q
        =
        
          
            2
            D
            K
            
              /
            
            h
          
        
        ,
      
    
    {\textstyle Q={\sqrt {2DK/h}},}
  
 which provides the cost minimum $T_{min}={\sqrt {2hDK}}+PD.$ === Example ===
Annual requirement quantity (D) = 10000 units
Cost per order (K) = 40
Cost per unit (P) = 50
Yearly carrying cost per unit = 4
Market interest = 2%
Economic order quantity = ${\sqrt {\frac {2D\cdot K}{h}}}$ = $={\sqrt {\frac {2\cdot 10000\cdot 40}{4+50\cdot 2\%}}}={\sqrt {\frac {2\cdot 10000\cdot 40}{5}}}$ = 400 units
Number of orders per year (based on EOQ) $={\frac {10000}{400}}=25$ Total cost $=P\cdot D+K(D/EOQ)+h(EOQ/2)$ Total cost $=50\cdot 10000+40\cdot (10000/400)+5\cdot (400/2)=502000$ If we check the total cost for any order quantity other than 400(=EOQ), we will see that the cost is higher.  For instance, supposing 500 units per order, then
Total cost $=50\cdot 10000+40\cdot (10000/500)+5\cdot (500/2)=502050$ Similarly, if we choose 300 for the order quantity, then
Total cost $=50\cdot 10000+40\cdot (10000/300)+5\cdot (300/2)=502083.33$ This illustrates that the economic order quantity is always in the best interests of the firm.

## Extensions

### Quantity discounts
An important extension to the EOQ model is to accommodate quantity discounts. There are two main types of quantity discounts: (1) all-units and (2) incremental. Here is a numerical example:

Incremental unit discount: Units 1–100 cost $30 each; Units 101–199 cost $28 each; Units 200 and up cost $26 each. So when 150 units are ordered, the total cost is $30*100 + $28*50.
All units discount: an order of 1–1000 units costs $50 each; an order of 1001–5000 units costs $45 each; an order of more than 5000 units costs $40 each. So when 1500 units are ordered, the total cost is $45*1500.
In order to find the optimal order quantity under different quantity discount schemes, one should use algorithms; these algorithms are developed under the assumption that the EOQ policy is still optimal with quantity discounts. Perera et al. (2017) establish this optimality and fully characterize the (s,S) optimality within the EOQ setting under general cost structures.

### Design of optimal quantity discount schedules
In presence of a strategic customer, who responds optimally to discount schedules, the design of an optimal quantity discount scheme by the supplier is complex and has to be done carefully. This is particularly so when the demand at the customer is itself uncertain. An interesting effect called the "reverse bullwhip" takes place where an increase in consumer demand uncertainty actually reduces order quantity uncertainty at the supplier.

### Backordering costs and multiple items
Several extensions can be made to the EOQ model, including backordering costs and multiple items. In the case backorders are permitted, the inventory carrying costs per cycle are: $IC\int \limits _{0}^{T_{1}}(Q-s-\lambda t)\,dt={\frac {IC}{2\lambda }}(Q-s)^{2},$ where s is the number of backorders when order quantity Q is delivered and $\lambda$ is the rate of demand. The backorder cost per cycle is: $\pi s+{\hat {\pi }}\int \limits _{0}^{T_{2}}\lambda tdt=\pi s+{\frac {1}{2}}{\hat {\pi }}\lambda T_{2}^{2}=\pi s+{\frac {{\hat {\pi }}s^{2}}{2\lambda }},$ where $\pi$ and ${\hat {\pi }}$ are backorder costs, $T_{2}=T-T_{1}$ , T being the cycle length and $T_{1}=(Q-s)/\lambda$ . The average annual variable cost is the sum of order costs, holding inventory costs and backorder costs: ${\mathcal {K}}={\frac {\lambda }{Q}}A+{\frac {1}{2Q}}IC(Q-s)^{2}+{\frac {1}{Q}}[\pi \lambda s+{\frac {1}{2}}{\hat {\pi }}s^{2}]$ To minimize ${\mathcal {K}}$ impose the partial derivatives equal to zero: ${\frac {\partial {\mathcal {K}}}{\partial Q}}=-{\frac {1}{Q^{2}}}\left[{\lambda }A+{\frac {1}{2}}IC(Q-s)^{2}+\pi \lambda s+{\frac {1}{2}}{\hat {\pi }}s^{2}\right]+{\frac {IC}{Q}}(Q-s)=0$ ∂ ${\frac {\partial {\mathcal {K}}}{\partial s}}=-{\frac {IC}{Q}}(Q-s)+{\frac {1}{Q}}\pi \lambda +{\frac {1}{Q}}{\hat {\pi }}s=0$ Substituting the second equation into the first gives the following quadratic equation: $[{\hat {\pi }}^{2}+{\hat {\pi }}IC]s^{2}+2\pi {\hat {\pi }}\lambda s+(\pi \lambda )^{2}-2\lambda AIC=0$ If ${\hat {\pi }}=0$ either s=0 or $s=\infty$ is optimal. In the first case the optimal lot is given by the classic EOQ formula, in the second case an order is never placed and minimum yearly cost is given by $\pi \lambda$ . If $\pi >{\sqrt {\frac {2AIC}{\lambda }}}=\delta$ or $\pi \lambda >K_{w}$ s $s^{*}=0$ is optimal, if $\pi <\delta$ then there shouldn't be any inventory system. If ${\hat {\pi }}\neq 0$ solving the preceding quadratic equation yields: $s^{*}=[{\hat {\pi }}+IC]^{-1}\left(-\pi \lambda +\left[(2\lambda AIC)\left(1+{\frac {IC}{\hat {\pi }}}\right)-{\frac {IC}{\hat {\pi }}}(\pi \lambda )^{2}\right]^{1/2}\right)$ Q $Q^{*}=\left[{\frac {{\hat {\pi }}+IC}{\hat {\pi }}}\right]^{1/2}\left[{\frac {2\lambda A}{IC}}-{\frac {(\pi \lambda )^{2}}{IC({\hat {\pi }}+IC)}}\right]^{1/2}$ If there are backorders, the reorder point is: $r_{h}^{*}=\mu -mQ^{*}-s^{*}$ ; with m being the largest integer $m\leq {\frac {\tau }{T}}$ and μ the lead time demand.
Additionally, the economic order interval can be determined from the EOQ and the economic production quantity model (which determines the optimal production quantity) can be determined in a similar fashion.
A version of the model, the Baumol-Tobin model, has also been used to determine the money demand function, where a person's holdings of money balances can be seen in a way parallel to a firm's holdings of inventory.
Malakooti (2013) has introduced the multi-criteria EOQ models where the criteria could be minimizing the total cost, Order quantity (inventory), and Shortages.
A version taking the time-value of money into account was developed by Trippi and Lewin.

### Imperfect quality
Another important extension of the EOQ model is to consider items with imperfect quality. Salameh and Jaber (2000) were the first to study the imperfect items in an EOQ model very thoroughly. They consider an inventory problem in which the demand is deterministic and there is a fraction of imperfect items in the lot and are screened by the buyer and sold by them at the end of the circle at discount price.

## Implementation
Dave Piasecki identifies two ways in which use of an EOQ approach may be implemented:

a spreadsheet method, whereby the EOQ for each stock item is calculated and recorded manually
entry of the EOQ formula into a new or existing inventory management system.
He suggests that a system-based implementation would be beneficial where the number of stock-keeping units is over around 2000. Annual updating of data and formulae are recommended. A hybrid system would involve downloading data into a spreadsheet for calculation purposes and then re-applying this data within the inventory system.

## Limitations
The EOQ model and its sister, the economic production quantity model (EPQ), have been criticised for "their restrictive set[s] of assumptions. Guga and Musa make use of the model for an Albanian business case study and conclude that the model is "perfect theoretically, but not very suitable from the practical perspective of this firm". However, James Cargal notes that the formula was developed when business calculations were undertaken "by hand", or using logarithmic tables or a slide rule. Use of spreadsheets and specialist software allows for more versatility in the use of the formula and adoption of "assumptions which are more realistic" than in the original model.
