# Théorie des files d'attente

> Source : Wikipédia (fr), « Théorie des files d'attente », révision 239910708 : https://fr.wikipedia.org/wiki/Th%C3%A9orie_des_files_d%27attente?oldid=239910708
> Licence : CC BY-SA 4.0 (attribution : contributeurs de Wikipédia). Texte brut converti, sections de références retirées.

La théorie des files d'attente est une théorie mathématique relevant du domaine des probabilités, qui étudie les solutions optimales de gestion des files d’attente, ou queues. Une queue est nécessaire et se créera d'elle-même si ce n'est pas anticipé, dans tous les cas où l'offre est inférieure à la demande, même temporairement. Elle peut s’appliquer à différentes situations : gestion des avions au décollage ou à l’atterrissage, attente des clients et des administrés aux guichets, ou bien encore stockage des programmes informatiques avant leur traitement. Ce domaine de recherches, né en 1917, des travaux de l’ingénieur danois Erlang sur la gestion des réseaux téléphoniques de Copenhague à partir de 1908, étudie notamment les systèmes d’arrivée dans une queue, les différentes priorités de chaque nouvel arrivant, ainsi que la modélisation statistique des temps d’exécution.
C'est grâce aux apports des mathématiciens Khintchine, Palm, Kendall, Pollaczek et Kolmogorov que la théorie s'est vraiment développée.

## Description
On définit un système d’attente de la manière suivante : un flux d’événements qu’on appellera « clients » arrive séquentiellement en réclamant un service. La théorie considère généralement le temps séparant l’arrivée des clients et la durée de service comme deux variables aléatoires (files dites « markoviennes »), mais certains travaux considèrent plutôt les files déterministes, où le temps d'attente est constant. Le client se dirige vers un poste de service (serveur) dès qu’il y en a un de libre, afin d’être servi, sinon il se positionne dans une « file d’attente. »     
Un système d’attente est donc composé d’un espace de service (comportant un ou plusieurs serveurs) et d'un espace d'attente dans lequel se forme une éventuelle file d'attente. En informatique, on parlera de client et de serveur ; ailleurs on préférera les termes d’unité et de station.
La littérature distingue par ailleurs :

les systèmes ouverts, où la file (le nombre d'entrées en attente) est de longueur infinie, et
les systèmes fermés, où la file d'attente est de taille finie.
Enfin, la description d'une file d'attente s'accompagne de la « discipline » ou « politique de service » :

file FIFO (First In, First Out) : premier (client) arrivé, premier servi
pile LIFO (Last in, first out) : dernier arrivé, premier servi ;
client le plus proche d'un serveur libre, ou Nearest neighbour

## Objet de la théorie
Étant donné une file d'attente, la théorie se propose de produire un certain nombre de résultats, tels :

la longueur moyenne de la file,
la durée moyenne de service
le taux moyen d'inactivité des serveurs,
le temps moyen d'attente dans une file
le temps moyen total de service dans le système (ou « temps de résidence » en informatique).
Elle peut étudier l'existence ou non d'un régime stationnaire, le risque de saturation du service, la discipline optimale par rapport au temps de résidence, etc.

## Aspects mathématiques

### Loi de Little
La loi de Little énonce que le nombre moyen  de clients dans un système stable est égal à leur fréquence moyenne d'arrivée  multipliée par leur temps moyen  passé dans le système : .
Quoique cet énoncé paraisse évident intuitivement, il n'en est pas moins remarquable, puisqu'il ne dépend ni du processus d'arrivée, ni de la discipline de service. Il s'applique également à des serveurs à l'intérieur d'un serveur ; la seule exigence est que le système soit stable et non-préemptif, ce qui exclut des états de transition comme la mise en route ou l'arrêt d'un serveur.
Dans certains cas, il est possible non seulement de relier la taille moyenne de la file d'attente au temps moyen d'attente, mais même de relier la loi de probabilité (et ses moments) de la taille de la file d'attente à celle du temps moyen d'attente.
Dans son article original de 1954, Little énonçait cette relation sans la démontrer. Il en donna une première démonstration en  1961, simplifiée depuis par Jewell et Eilon.

### Notation de Kendall

Il existe de très nombreux systèmes de files d'attente.
La notation de Kendall permet de décrire le système par une suite de 6 symboles a/s/C/K/m/Z.

a indique la loi de probabilité des instants d'arrivées, par exemple GI pour la loi générale indépendante et M pour la loi de Poisson ou la loi exponentielle.
s indique la loi de probabilité de la durée du service (au guichet) ; on utilise les mêmes symboles que précédemment
C indique le nombre de serveurs (nombre de guichets)
K, c'est la capacité totale du système, c'est-à-dire le nombre C de serveurs + le nombre de places en attente
m indique la population totale de clients (par exemple : nombre d'inscrits sur une liste électorale dans le cas d'une file d'attente à un bureau de vote)
Z, la discipline de service, par exemple FIFO (first in, first out), LIFO (Last in, first out), Nearest neighbour, etc.
Très souvent, K est infini, m est infini, et Z en FIFO (encore dénoté par peps). Dans ce cas, les trois derniers symboles de la notation sont omis. 

### Quelques résultats
Avec : 

 fréquence moyenne d'arrivées ;
 temps moyen de service ;
 trafic offert (nombre moyen d'arrivées pendant le temps moyen de service). Attention à ne pas oublier S, le nombre de serveurs.
