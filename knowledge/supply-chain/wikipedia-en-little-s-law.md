# Little's law

> Source : Wikipédia (en), « Little's law », révision 1370351232 : https://en.wikipedia.org/wiki/Little%27s_law?oldid=1370351232
> Licence : CC BY-SA 4.0 (attribution : contributeurs de Wikipédia). Texte brut converti, sections de références retirées.

In mathematical queueing theory, Little's law (also result, theorem, lemma, or formula) is a theorem by John Little which states that the long-term average number of customers (L) in a stationary system is equal to the long-term average effective arrival rate (λ) multiplied by the average time that a customer spends in the system (W). Expressed algebraically the law is $L=\lambda W.$ The relationship is not influenced by the arrival process distribution, the service distribution, the service order, or practically anything else. In most queuing systems, service time is the bottleneck that creates the queue.
The result applies to any system, and particularly, it applies to systems within systems. For example in a bank branch, the customer line might be one subsystem, and each of the tellers another subsystem, and Little's result could be applied to each one, as well as the whole thing. The only requirement is that the system be ergodic.
In some cases it is possible not only to mathematically relate  the average number in the system to the average wait but even to relate the entire probability distribution (and moments) of the number in the system to the wait.

## History
In a 1954 paper, Little's law was assumed true and used without proof. The form L = λW was first published by Philip M. Morse where he challenged readers to find a situation where the relationship did not hold. Little published  in 1961 his proof of the law, showing that no such situation existed. Little's proof was followed by a simpler version by Jewell and another by Eilon. Shaler Stidham published a different and more intuitive proof in 1972.

## Examples

### Finding response time
Imagine an application that had no easy way to measure response time. If the mean number in the system and the throughput are known, the average response time can be found using Little’s Law:

mean response time = mean number in system / mean throughput
For example: A queue depth meter shows an average of nine jobs waiting to be serviced. Add one for the job being serviced, so there is an average of ten jobs in the system. Another meter shows a mean throughput of 50 per second. The mean response time is calculated as 0.2 seconds = 10 / 50 per second.

### Customers in the store
Imagine a small store with a single counter and an area for browsing, where only one person can be at the counter at a time, and no one leaves without buying something.  So the system is:

entrance → browsing → counter → exit
If the rate at which people enter the store (called the arrival rate) is the rate at which they exit (called the exit rate), the system is stable.  By contrast, an arrival rate exceeding an exit rate would represent an unstable system, where the number of waiting customers in the store would gradually increase towards infinity.
Little's Law tells us that the average number of customers in the store L, is the effective arrival rate λ, times the average time that a customer spends in the store W, or simply: $L=\lambda W$ Assume customers arrive at the rate of 10 per hour and stay an average of 0.5 hour.  This means we should find the average number of customers in the store at any time to be 5. $L=10\times 0.5=5$ Now suppose the store is considering doing more advertising to raise the arrival rate to 20 per hour.  The store must either be prepared to host an average of 10 occupants or must reduce the time each customer spends in the store to 0.25 hour.  The store might achieve the latter by ringing up the bill faster or by adding more counters.
We can apply Little's Law to systems within the store.  For example, consider the counter and its queue.  Assume we notice that there are on average 2 customers in the queue and at the counter.  We know the arrival rate is 10 per hour, so customers must be spending 0.2 hours on average checking out. $W={\frac {L}{\lambda }}={\frac {2}{10}}=0.2$ We can even apply Little's Law to the counter itself.  The average number of people at the counter would be in the range (0, 1) since no more than one person can be at the counter at a time.  In that case, the average number of people at the counter is also known as the utilisation of the counter.
However, because a store in reality generally has a limited amount of space, it can eventually become unstable. If the arrival rate is much greater than the exit rate, the store will eventually start to overflow, and thus any new arriving customers will simply be rejected (and forced to go somewhere else or try again later) until there is once again free space available in the store. This is also the difference between the arrival rate and the effective arrival rate, where the arrival rate roughly corresponds to the rate at which customers arrive at the store, whereas the effective arrival rate corresponds to the rate at which customers enter the store. However, in a system with an infinite size and no loss, the two are equal.

## Estimating parameters
To use Little's law on data, formulas must be used to estimate the parameters, as the result does not necessarily directly apply over finite time intervals, due to problems like how to log customers already present at the start of the logging interval and those who have not yet departed when logging stops.

## Applications
Little's law is widely used in manufacturing to predict lead time based on the production rate and the amount of work-in-process.
Software-performance testers have used Little's law to ensure that the observed performance results are not due to bottlenecks imposed by the testing apparatus.
Other applications include staffing emergency departments in hospitals.
Lastly, an equivalent version of Little's law also applies in the fields of demography and population biology, although not referred to as "Little's Law". For example, Cohen (2008) explains that in a homogeneous stationary population without migration, $P=B\times e$ , where $P$ is the total population size, $B$ is the number of births per year, and $e$ is the life expectancy from birth. The formula $P=B\times e$ is thus directly equivalent to Little's law ( $L=\lambda \times W$ ). However, biological populations tend to be dynamic and therefore more complicated to model accurately.

## Distributional form
In some cases, it is possible not only to relate averages but to relate the entire probability distribution of the number in the system to the time in the system under a first come, first served discipline. A distributional relation for many FIFO/Poisson-class systems was derived by Keilson and Servi (1988) and further developed in related work, including links to the Fuhrmann–Cooper decomposition; later, Bertsimas and Nakazato (1995) provided a new proof and surveyed applications.
