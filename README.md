In this script. I am trying to merge villages from Romania from 1930 to villages from Romania in 1956, based on two distances:
-semantic
-geographic

Steps:
>1.I first identify all the 1930 villages that are within a 15km-radius from every village in 1956
>2.I calculate the distance in km from every 1956 village to the 1930 villages
>3.I finally perform a fuzzy semantic match between the name of the village in 1956 and "best" matching item in the list of closest villages from 1930.//

