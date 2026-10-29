# Overall equipment effectiveness

> Source : Wikipédia (en), « Overall equipment effectiveness », révision 1372274508 : https://en.wikipedia.org/wiki/Overall_equipment_effectiveness?oldid=1372274508
> Licence : CC BY-SA 4.0 (attribution : contributeurs de Wikipédia). Texte brut converti, sections de références retirées.

Overall equipment effectiveness (OEE) is a measure of how well a manufacturing equipment is utilized compared to its full potential, during the periods when it is scheduled to run. 
It identifies the percentage of manufacturing time that is truly productive as well as the time it is losing effectiveness. An OEE of 100% means that only good parts are produced (100% quality), at the maximum speed (100% performance), and without interruption (100% availability).

## Introduction
Measuring OEE is a manufacturing best practice. By measuring OEE and the underlying losses, important insights can be gained on how to systematically improve the manufacturing process.
Technically, OEE is an effective metric for identifying and visualizing losses, and steering the improvement of the effectiveness of manufacturing equipment by eliminating 'waste'.
Socially, OEE can provide a common language for groups speaking in different 'languages' such as shop floor (units), managers (money) or planners (time).

## Origin of OEE
The term OEE was first mentioned in Seiichi Nakajima's book 'TPM Tenkai' in 1982. OEE was described as a central part of the Total Productive Maintenance methodology. It is based on the Harrington Emerson way of thinking regarding labor efficiency.

## Essence of OEE
100% OEE is considered to be a theoretical reference point where a machine would be permanently running, at its theoretical maximal speed, producing only good products. Anything hindering this is considered to be a 'loss'. To gain insight into which losses occur on the equipment and to target the areas that should be improved to increase the value-creating conversion (effectiveness), three questions are asked:

Is the machine running? If not: What was hindering?
When running: Is the machine running at theoretical maximal speed? If not: What was slowing it down?
Is the output meeting its specifications? If not: what DID come out?
The first question leads to the 'availability rate' of the equipment, the second one to the 'performance rate' and the third one to the 'quality rate'.
in this way, a cascade of effectiveness and effectiveness losses arises.

### Loss cascade
The quality rate refers to a part of the performance (the part that there was 'speed', the other part is lost in the performance rate). The Performance rate refers to part of the availability (the time there was output - the other part is lost in the availability rate).

### Three 'rates'
The OEE can now be calculated as the product of the three separate components:

 Availability: percentage of scheduled time that the equipment is available to operate. The Availability Metric is a pure measurement of Uptime that is designed to exclude the effects of Quality and Performance. The losses due to wasted availability (time) are called availability losses.
 Performance: speed at which the equipment runs as a percentage of its theoretical maximal speed. The losses due to wasted speed (amount of output) are called performance losses. The performance rate is designed to exclude the effects of Quality and Availability. It will disclose:
deliberately reduced speed
deviation from the set speed due to minor stops (i.e., downtime smaller than a threshold and thus not included in availability)
speed fluctuations.
 Quality: Good Units produced as a percentage of the Total units produced. It is commonly referred to as the first pass yield (FPY), First Time Right (FTR), or First Time Quality (FTQ). The losses due to wasted quality (good product) are called quality losses.
Each of the three components of the OEE points to an aspect of the process that can be targeted for improvement. 
OEE may be applied to any individual equipment or line. This tool also allows for drilling down for very specific analysis, such as a particular Time frame, Shift, Team or any of several other parameters.
Although the performance of a particular product can be determined from OEE data, OEE cannot be calculated for that product because this would require that all downtime (availability losses) should be correlated to specific products.

### Six Big Losses
OEE focusses on the 'if not' in the equations: Where did potential effectiveness got lost? These 'losses' of effectiveness are being subdivided further into what is known as the 'Six Big Losses' to OEE.
In order to make this more universally applicable and also to better reflect the financial impact of the losses, the original six big losses were later adjusted slightly.

The reason for identifying the losses in these categories is so that specific countermeasures can be applied to reduce the loss and improve the overall OEE.

## Calculation of OEE
Multiplying the three underlying grades AxPxQ results in a percentage value that indicates the proportion of the scheduled machine running time during which production actually met the quality criteria.
This value is always well below 100%, as 100% is a theoretical value. Even if a system runs continuously at maximum speed without causing a single defect, it will for example still need to be serviced at some point. 

OEE is calculated with the formula: $OEE=Availability*Performance*Quality$ Example: (Availability= 86.6%)*(Performance=93%)*(Quality=91.3%)= (OEE=73.6%)

### Alternative calculation
Alternatively, the OEE as a number could be calculated by dividing the minimum time needed to produce the parts under optimal conditions by the actual time needed to produce the parts.
However, in this way the losses are no longer known, meaning the most important part of OEE is missing.

### Value Range
The value range for OEE is between 0% and 100%. If an effectiveness level of more than 100% is displayed, this indicates an error in the definition.
100% time for OEE is the time when the machine is scheduled to be in operation: This is usually the "shift time."

### Availability
The Availability portion of the OEE Metric represents the percentage of scheduled time (also referred to as 'loading time') that the equipment is available to operate.

#### Example
A given machine is scheduled to run for an 8-hour (480-minute) shift with a 30-minute  break, during which the machine is being stopped, and there is a breakdown of 60 minutes.
During the scheduled operating time of 480 minutes, the machine was waiting 30 min. because of the break and 60 minutes because it broke down.
It was actually operating 480 - 30 - 60 = 390 Minutes

#### Calculation
Method 1: $Availability=operating\ time/scheduled\ time$ Example: Availability = 390 minutes / 480 minutes = 81.25%

Method 2: $Availability=(loading\ time-downtime)/loading\ time$ Example: Availability = (480 – 90 minutes) / 480 minutes = 81.25%

### Performance
The performance rate represents the ratio between the theoretical maximum speed of the machine and its actual speed.
Performance can only be calculated when there is output; thus during actual running time.

#### Defining the maximum speed
While the actual performance can be measured, it is often difficult in operational practice to obtain the theoretical maximum speed as a reference value. The technical data provided by the machine manufacturer does not usually correspond to the theoretically possible maximum values, e.g. to avoid complaints or for other reasons.
Defining a too low maximum speed will become visible when the performance goes above 100%, which is undesirable. Ultimately, the goal of OEE is to reveal all potential.
It is a good practice to calculate the maximum value based on physical limits, e.g., a calculation of heat transfer, the power of a motor, or the fall speed of a product. If that fails, the concept of "best demonstrated cycle time" has proven itself. This involves determining the production speeds of products from the past and increasing the highest production speed by a margin of 20%. Defining this as 100% performance may lead to a structurally too low OEE, however it will visualize any potential loss on the performance.
The factor 1 (100%) now represents a peak value that is never exceeded, even for a short time.
For systems that only manufacture one or a few products, calculating the performance factor is simple. If a large number of different products with different maximum speeds are run on one system (multi-product companies), the effort required to determine the maximum speed can be high and the performance should be calculated correctly using a weighted average.

#### Calculation
The Performance is calculated with formula: $Performance={\frac {Parts\ produced*Ideal\ cycle\ time}{Operating\ time}}$ ==== Example ====
A given equipment is scheduled to run for an 8-hour (480-minute) and has 90 min downtime.

Operating Time = 480 Min – 90 Min Downtime = 390 Minutes

The Standard Rate for the part being produced is 40 Units/Hour or 1.5 Minutes/Unit
The equipment produces 242 Total Units during the shift. Note: The basis is Total Units, not Good Units. The Performance metric does not penalize for Quality.
Time to Produce Parts = 242 Units * 1.5 Minutes/Unit = 363 Minutes

Performance = 363 Minutes / 390 Minutes = 93.1%

### Quality
The Quality portion of the OEE Metric represents the Good Units produced as a percentage of the Total Units produced. The Quality Metric is a pure measurement of Process Yield that is designed to exclude the effects of Availability and Performance. The losses due to defects and rework are called quality losses.
Calculation: The Quality is calculated with the formula: $Quality={\frac {Units\ produced-Defective\ units}{Units\ produced}}$ Example:
242 Units are produced. 21 are defective.

(242 units produced - 21 defective units) = 221 units

221 good units / 242 total units produced = 91.32%

## Standards
The calculations of OEE may not seem to be particularly complicated, but care must be taken as to standards that are used as the basis. In order to visualize all losses, it is crucial to use the right 'configuration' of the metric.

### ISO 22400-2:2014 and VDI 3423:2011-08 (2011)
Definitions — for parts — of the OEE can be found in ISO 22400-2:2014. and VDI 3423:2011-08 (2011)
These definitions are not standardized for all industries and are individually tailored to the respective company in its application. Furthermore, the ISO 22400 standard presents two different OEE versions that appear to be inconsistent with one another, the first of which – in the standard's normative section – contains no reference to or connection with the original Nakajima's Total Productive Maintenance (TPM) model. To resolve this ambiguity, academic literature provides a comprehensive classification framework that maps the standard's time elements to the traditional OEE formula, ensuring consistency between the ISO standard and established industrial practices.

### OEE Industry Standard
This to OEE dedicated standard aims for the visualisation of all effectiveness losses on any manufacturing equipment, being  unabigiously clear to production personnel. The standard uses the same logic and uniform terminology for any type of equipment.

## Data collection
In order to calculate OEE, operational data needs to be acquired from the production process. This needs to reflect 'what happened' on one hand, and 'what did not happen' (the losses) on the other hand. When this data is not present to the level required to make a meaningful OEE calculation, roughly two strategies can be followed:

### Automatic data collection
Depending on the systems or products, it can be difficult to collect the basic data required to determine the key figure. Many companies therefore rely on special software for data collection.

Advantage: Downtimes and production figures are recorded accurately (e.g. by sensors).
Disadvantage: Operators can be bypassed and the reasons for downtimes or rejects are not recorded correctly

### Manual or semi-automatic data collection
Although manual recording by the operator can be considered to be time-consuming and inaccurate, it has some significant advantages

Operators can take responsibility for recording their own actions and thus indicate what is stopping them on the basis of numerical data facts. With proper monitoring, stoppages and rejections become more reliable.
can be started within days.
Disadvantage: The recording of standstill reasons and numbers produced can be less accurate.

## OEE and continuous improvement

### Total Productive Maintenance
The goal of TPM (Total Productive Maintenance) as set out by Seiichi Nakajima, is "The continuous improvement of OEE by engaging all those that impact on it in small group activities". To achieve this, the TPM toolbox sets out a Focused improvement tactic to reduce each of the six types of OEE loss. For example, the Focused improvement tactic to systematically reduce breakdown risk sets out how to improve asset condition and standardise working methods to reduce human error and accelerated wear. Zero Failure Management provides a profound structure to achieve this.

#### OEE and Focused Improvement
Combining OEE with Focused improvement converts OEE from a lagging to a leading indicator that can be used to guide performance management priorities.
The first Focused improvement stage of OEE improvement is to achieve a stable OEE, i.e. one which varies at around 5% from the mean for a representative production sample. This indicates that the asset performance is stable and not affected by variability in equipment wear rates and working methods.
The second stage of OEE improvement (optimisation) is meant to remove chronic losses. 
As the TPM process delivers these gains through small cross functional improvement teams, the process of OEE improvement should also raise front line team engagement, problem ownership, collaboration and skill levels.
This combination of OEE as a KPI, TPM Focused improvement tactics and front line team engagement is intended to make the gains sustainable and deliver the TPM goal of year on year improvement in OEE. Zero Failure Management helps significantly to achieve this.

### OEE and Lean Manufacturing
OEE measurement is also commonly used as a key performance indicator (KPI) in conjunction with lean manufacturing efforts. To achieve the main goal of Lean, creating flow, individual pieces of equipment need to be fully reliable and in tune.

## Derived measures

### Total effective equipment performance
Total effective equipment performance (TEEP) is a closely to OEE related measure. TEEP quantifies OEE against calendar hours rather than only against scheduled operating hours. A TEEP of 100% means that the operations have run with an OEE of 100% 24 hours a day and 365 days a year (100% loading).
TEEP, therefore, reports the 'bottom line' effectiveness of manufacturing equipment.

#### Calculation for TEEP
To calculate the Total Effective Equipment Performance(TEEP), the OEE is multiplied by a fourth component: Loading. $TEEP=Loading\ rate*OEE\$ === Loading rate ===
The Loading rate of the TEEP Metric represents the percentage of time that the equipment is scheduled to operate compared to the total Calendar Time that is available. The Loading Metric is a pure measurement of Schedule effectiveness and is designed to exclude the effects how well that equipment may perform.

==== Calculation ==== $Loading=Scheduled\ time/Calendar\ time$ Example:
A given equipment is scheduled to run 5 Days per Week, 24 Hours per Day.
For a given week, the Total Calendar Time is 7 Days at 24 Hours.

Loading  = (5 days x 24 hours) / (7 days x 24 hours) = 71.4%

### Overall Operations Effectiveness
Where TEEP includes ALL time (so also time the machine was never scheduled to run), OOE includes time that initially had been scheduled, but where the equipment was un-scheduled later on; usually for reasons outside the span of control of the shop floor team:

lack of orders
strikes
pandemic
Where in OEE availabilty is calculated based on the scheduled (shift) time, in OOE the availability is calculated based on the scheduled PLUS the un-scheduled time (not to be confused with the NOT scheduled time as in TEEP)

#### Calculation
Availability in OOE: $AvailabilityOOE={\frac {RunningTime+WaitingTime+BreakdownTime+UnscheduledTime}{ScheduledTime}}$ == Benefits ==
The advantage of OEE lies in the transparency of the value added share and the associated losses of the equipment.

Management: OEE enables management to view the assets from a different perspective. The components of the key figure are suitable, for example, for linking a target agreement process with an increase in OEE, as its completeness makes it robust against structural changes in production.
Shop floor: Enables the shop floor to use facts and figures to determine what is preventing it from operating the machine optimally. When implemented correctly, operators can take more responsibility for their equipment, leading to greater personal accountability.
OEE can provide a common language for parties who normally use different terms/units.

## Common Issues with OEE

### Overall equipment efficiency or Overall equipment effectiveness?
The term "Overall Equipment Efficiency" is often wrongly used as a synonym for "Overall Equipment Effectiveness". Measures that increase production output but incur disproportionately high costs may well be effective, but at the same time they may be inefficient and therefore economically unviable and thus unproductive.

### The '85% is World Class' myth
To assume that 85% OEE is a "world Class" target value is in many cases incorrect:

Situation 1. Not all losses are included in the definition of the OEE: The OEE looks higher than it actually is.
Situation 2: Quality rate is low: continuously running at full speed, producing many rejects drives up costs.
Situation 3: OEE fluctuates, process is not in control: The average OEE does not reflects the deviations.
Situation 4. Stock increases: producing product not needed.
Situation 5: High effectiveness is achieved at low efficiency: More costs on input side.
Situation 6: High effectiveness is achieved without binding the workforce: risk for low sustainability on longer term.
Situation 7: 85% achieved, but it is not sustainable: Lack of a controlled situation.

### Detection of quality problems
Often, insufficient quality is not detected at the equipment that caused it. In this case, it has proven effective to apply the "discovery principle," i.e., to apply an OEE reduction to the equipment where the error was discovered. This removes the OEE from being purely equipment-related and turns it into a process indicator.
However, the OEE of a piece of equipment can of course also be optimized by making improvements to other equipment. The OEE should also be a key figure that is as up-to-date as possible. In this respect, the OK quantity should be determined at the latest at the end of the shift and the OEE calculated.
From the perspective of Process Control, the  question rises how an operator can be responsible for manufacturing correct products if he cannot see whether the products are correct.
To highlight this problem, it is worth considering blocked products as a quality issue: after all, they were not right the first time around.

### Changovers and maintenance
Valuable activities such as setup or maintenance will also reduce overall equipment effectiveness (OEE) at the beginning. If setup activities reduce overall equipment effectiveness, there is an incentive to reduce setup times using SMED (Single-minute exchange of die). On the other hand, this also means that OEE can be increased by reducing the number of changeovers, i.e. by increasing batch sizes. This would contradict the principles of lean production. This highlights the importance of a clear explanation of OEE: the goal is not to be as high as possible, but to identify obstacles and then eliminate them.

### Threshold for Standstills
A convention must be agreed within the company to define when downtime occurs. Recording and justifying every second of equipment downtime is too time-consuming for most companies. In practice, a recording limit of 1 to 5 minutes of equipment downtime has proven to be a pragmatic approach. All downtimes of less than one minute are therefore included in the performance rate.

### Data processing
The collected data must be processed in order to obtain meaningful information. This information is aimed at various target groups, such as.

The people who operate the system on a daily basis.
The people who maintain the system.
The people who take care of the logistical process.
People who are responsible for investments in new equipment and expensive operating resources.
Managers.
Meaningful analyses prove to be the key to good decisions. Theoretically, this is only possible with very precise figures. In practice, it has been shown that correctly selected data has a greater effect in this respect than high precision.

### Using OEE for comparison and benchmarking
Although tempting, OEE (as a number) is NOT suitable for comparing machines or benchmarking.
Consider this situation:

Early shift on machine X has an OEE of  56%.
Late shift on machine X also has an OEE of 56%.
Are they the same?

Early shift was running an availability of 75%, Performance of 85% and quality of 95%.
Late shift was running an availability of  85%, Performance of 95% and quality of 75%.
For similar reasons, OEE may not be applied to aggregate to Department or Plant levels.

### Interlinked equipment
Where multiple machines are linked together, each individual piece of equipment will display the waiting categories "No Input" (Starved) and "No output" (Blocked) in addition to the standard standstill reasons. This allows upstream or downstream faults in production equipment to be identified.

### Using OEE as a Heuristic
The use of OEE requires knowledge of manufacturing environments and understanding of the underlying data. Without this, a specific OEE number may be of little to no value.

#### Measuring employees
OEE cannot be used to measure employee performance. It is used to identify and measure equipment losses, which can then be eliminated through appropriate root cause analysis and measures.
Using OEE as a heuristic is not recommended.

#### Examples
It may be far more costly to run a facility at certain times.
Performance and quality may not be independent of each other or of availability and loading.
Used definitions are often quite different
When not correctly implemented, parties may experience an incentive in fudging numbers
OEE has properties of a geometric mean.  As such it punishes variability among its subcomponents.  For example, 20% * 80% = 16%, whereas 50% * 50% = 25%.
Costs associated with several components of OEE are mostly asymmetric. A correct translation from OEE to finance must be made.
Consider a system where the cost of error is exceptionally high. In such a condition, higher quality may be far more important in a proper evaluation of efficiency than performance or availability.
OEE also to some extent assumes a closed system and a potentially static one. If one can bring in additional resources (or lease out unused resources to other projects or business units) then it may be more appropriate for example to use an expected net present value analysis.
Variability in flow can also introduce important costs and risks that may merit further modeling. Sensitivity analysis and measures of change may be helpful.
