# Availability

> Source : Wikipédia (en), « Availability », révision 1378432007 : https://en.wikipedia.org/wiki/Availability?oldid=1378432007
> Licence : CC BY-SA 4.0 (attribution : contributeurs de Wikipédia). Texte brut converti, sections de références retirées.

In reliability engineering, the term availability has the following meanings:

The degree to which a system, subsystem or equipment is in a specified operable and committable state at the start of a mission, when the mission is called for at an unknown, i.e., a random, time.
The probability that an item will operate satisfactorily at a given point in time when used under stated conditions in an ideal support environment.
Normally high availability systems might be specified as 99.98%, 99.999% or 99.9996%. The converse, unavailability, is 1 minus the availability.

## Representation
The simplest representation of availability (A) is a ratio of the expected value of the uptime of a system to the aggregate of the expected values of up and down time (that results in the "total amount of time" C of the observation window) $A={\frac {E[\mathrm {uptime} ]}{E[\mathrm {uptime} ]+E[\mathrm {downtime} ]}}={\frac {E[\mathrm {uptime} ]}{C}}$ Another equation for availability (A) is a ratio of the Mean Time To Failure (MTTF) and Mean Time Between Failure (MTBF), or $A={\frac {MTTF}{MTTF+MTTR}}={\frac {MTTF}{MTBF}}$ If we define the status function $X(t)$ as $X(t)={\begin{cases}1,&{\text{sys functions at time }}t\\0,&{\text{maintenance}}\end{cases}}$ therefore, the availability A(t) at time t > 0 is represented by $A(t)=\Pr[X(t)=1]=E[X(t)].\,$ Average availability must be defined on an interval of the real line. If we consider an arbitrary constant $c>0$ , then average availability is represented as $A_{c}={\frac {1}{c}}\int _{0}^{c}A(t)\,dt.$ Limiting (or steady-state) availability is represented by $A=\lim _{c\rightarrow \infty }A_{c}.$ Limiting average availability is also defined on an interval $[0,c]$ as, $A_{\infty }=\lim _{c\rightarrow \infty }A_{c}=\lim _{c\rightarrow \infty }{\frac {1}{c}}\int _{0}^{c}A(t)\,dt,\quad c>0.$ Availability is the probability that an item will be in an operable and committable state at the start of a mission when the mission is called for at a random time, and is generally defined as uptime divided by total time (uptime plus downtime).

### Series vs Parallel components

Let's say a series component is composed of components A, B and C. Then the following formula applies: 
Availability of series component = (availability of component A) x (availability of component B) x (availability of component C)
Therefore, the combined availability of multiple components in a series is always lower than the availability of individual components. 
On the other hand, the following formula applies to parallel components:
Availability of parallel components = 1 - (1 - availability of component A) X (1 - availability of component B) X (1 - availability of component C)

In corollary, if you have N parallel components each having X availability, then:
Availability of parallel components = $1-(1-X)^{N}$ Using parallel components can exponentially increase the availability of the overall system.  For example, if each of your hosts has only 50% availability, by using 10 of hosts in parallel, you can achieve 99.9023% availability.
Note that redundancy doesn’t always lead to higher availability. In fact, redundancy increases complexity, which in turn reduces availability. According to Marc Brooker, to take advantage of redundancy, ensure that:

You achieve a net-positive improvement in the overall availability of your system
Your redundant components fail independently
Your system can reliably detect healthy redundant components
Your system can reliably scale out and scale in redundant components.

### Methods and techniques to model availability
Reliability Block Diagrams or Fault Tree Analysis are developed to calculate availability of a system or a functional failure condition within a system, including many factors like:

Reliability models
Maintainability models
Maintenance concepts
Redundancy
Common cause failure
Diagnostics
Level of repair
Repair status
Dormant failures
Test coverage
Active operational times, missions and subsystem states
Logistical aspects like spare part (stocking) levels at different depots, transport times, repair times at different repair lines, manpower availability and more.
Uncertainty in parameters
Furthermore, these methods are capable of identifying the most critical items and failure modes or events that impact availability.

### Definitions within systems engineering
Availability, inherent (Ai) 
The probability that an item will operate satisfactorily at a given point in time when used under stated conditions in an ideal support environment. It excludes logistics time, waiting or administrative downtime, and preventive maintenance downtime. It includes corrective maintenance downtime. 
Inherent availability is generally derived from an analysis of an engineering design:

The impact of a repairable element on the availability of the system, in which it operates, equals mean time between failures MTBF/(MTBF+ mean time to repair MTTR).
The impact of a one-off/non-repairable element (could be refurbished/remanufactured) on the availability of the system, in which it operates, equals the mean time to failure (MTTF)/(MTTF + the mean time to repair MTTR).
It is based on quantities under the control of the designer.
Availability, achieved (Aa)  
The probability that an item will operate satisfactorily at a given 
point in time when used under stated conditions in an ideal support environment (i.e., that personnel, tools, spares, etc., are instantaneously available). It excludes logistics time and waiting or administrative downtime. 
It includes active preventive and corrective maintenance downtime.
Availability, operational (Ao) 
The probability that an item will operate satisfactorily at a given point in time when used in an actual or realistic operating and support environment. It includes logistics time, ready time, and waiting or administrative downtime, and both preventive and corrective maintenance downtime. This value is equal to the mean time between failure (MTBF) divided by the mean time between failure plus the mean downtime (MDT). This measure extends the definition of availability to elements controlled by the logisticians and mission planners such as quantity and proximity of spares, tools and manpower to the hardware item.
Refer to Systems engineering for more details

### Basic example
If we are using equipment which has a mean time to failure (MTTF) of 81.5 years and mean time to repair (MTTR) of 1 hour:

MTTF in hours = 81.5 × 365 × 24 = 713940 (This is a reliability parameter and often has a high level of uncertainty!)
Inherent availability (Ai) = 713940 / (713940+1) = 713940 / 713941 = 99.999860%
Inherent unavailability = 1 / 713940 = 0.000140%
Outage due to equipment in hours per year = 1/rate = 1/MTTF = 0.01235 hours per year.

## Literature
Availability is well established in the literature of stochastic modeling and optimal maintenance. Barlow and Proschan [1975] define availability of a repairable system as "the probability that the system is operating at a specified time t." Blanchard [1998] gives a qualitative definition of availability as "a measure of the degree of a system which is in the operable and committable state at the start of mission when the mission is called for at an unknown random point in time." This definition comes from the MIL-STD-721. Lie, Hwang, and Tillman [1977] developed a complete survey along with a systematic classification of availability.
Availability measures are classified by either the time interval of interest or the mechanisms for the system downtime. If the time interval of interest is the primary concern, we consider instantaneous, limiting, average, and limiting average availability. The aforementioned definitions are developed in Barlow and Proschan [1975], Lie, Hwang, and Tillman [1977], and Nachlas [1998]. The second primary classification for availability is contingent on the various mechanisms for downtime, such as the inherent availability, achieved availability, and operational availability. (Blanchard [1998], Lie, Hwang, and Tillman [1977]). Mi [1998] gives some comparison results of availability considering inherent availability.
Availability considered in maintenance modeling can be found in Barlow and Proschan [1975] for replacement models, Fawzi and Hawkes [1991] for an R-out-of-N system with spares and repairs, Fawzi and Hawkes [1990] for a series system with replacement and repair, Iyer [1992] for imperfect repair models, Murdock [1995] for age replacement preventive maintenance models, Nachlas [1998, 1989] for preventive maintenance models, and Wang and Pham [1996] for imperfect maintenance models. A very comprehensive recent book is by Trivedi and Bobbio [2017].

## Applications
Availability factor is used extensively in power plant engineering. For example, the North American Electric Reliability Corporation implemented the Generating Availability Data System in 1982.
