
##############################################
#YOU SHOULD FIRST DO THIS IN COMMAND PROMPT:
#This installs fuzzywuzzy, which is necessary for the Levenstein distance
#C:\Python27\ArcGIS10.6\Scripts\pip.exe install python-Levenshtein
#####################################

# Import arcpy module
import arcpy
import os
import pandas as pd
import numpy as np
import unicodedata
from fuzzywuzzy import fuzz
from fuzzywuzzy import process

#In this script. I am trying to merge villages from Romania from 1930 to villages from Romania in 1956, based on two distances:
#-semantic
#-geographic

#Steps
#1.I first identify all the 1930 villages that are within a 15km-radius from every village in 1956
#2.I calculate the distance in km from every 1956 village to the 1930 villages
#3.I finally perform a fuzzy semantic match between the name of the village in 1956 and "best" matching item in the list of closest villages from 1930.

arcpy.env.overwriteOutput = True

# Local variables:
path = "C:\\Users\\bogdanp\\Dropbox\\Romania collectivization\\"


######################################################
#Step 1: Making a GDB Database and Copying Shapefiles#
######################################################
# Process: Create File GDB
arcpy.CreateFileGDB_management(path, "Data\\upwork\\razvan\\census_1930_part1\\levestein", "CURRENT")
arcpy.env.workspace = path + "Data\\upwork\\razvan\\census_1930_part1\\levestein.gdb"
villages_1930 = path + "Data\upwork\\razvan\\census_1930_part1\\polygons_intersect.gdb\\villages_1930"
villages_1930_2 = path + "Data\\upwork\\razvan\\census_1930_part1\\levestein.gdb\\villages_1930"

villages_1956 = path + "Data\upwork\\razvan\\census_1930_part1\\polygons_intersect.gdb\\villages_1956"
villages_1956_2 = path + "Data\\upwork\\razvan\\census_1930_part1\\levestein.gdb\\villages_1956"
villages_1956_pt = path + "Data\\upwork\\razvan\\census_1930_part1\\levestein.gdb\\villages_1956_pt"


arcpy.CopyFeatures_management(villages_1930, villages_1930_2, "", "0", "0", "0")
arcpy.CopyFeatures_management(villages_1956, villages_1956_2, "", "0", "0", "0")

############################################################################################
#Step 2: Calculating the area of the 1956 villages - helpful for later transformations in R#
############################################################################################
# Process: Add Field
arcpy.AddField_management(villages_1956_2, "area_1956", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
arcpy.CalculateField_management(villages_1956_2, "area_1956", "[Shape_Area]", "VB", "")
print "Added the 1956 area"

#######################################
#Step 3: Converting polygons to points#
#######################################
# Process: Feature To Point
arcpy.FeatureToPoint_management(villages_1956_2, villages_1956_pt, "INSIDE")
arcpy.AddXY_management(villages_1956_pt)
print "Added XY coordinates"


################################################################
#Step 4: Creating pandas dataframes with the relevant variables#
################################################################
SC = path + "Data\\upwork\\razvan\\census_1930_part1\\levestein.gdb\\villages_1930"
only_relevant_fields = ['original_order', 'final_lat', 'final_lon', 'village_no_diacritics']
villages_1930_df = pd.DataFrame(arcpy.da.TableToNumPyArray(SC, only_relevant_fields))

SC = path + "Data\\upwork\\razvan\\census_1930_part1\\levestein.gdb\\villages_1956_pt"
only_relevant_fields = ['ID_1956', 'uniqueID', 'POINT_Y', 'POINT_X', 'village_1962_no_diacritics']
villages_1956_df = pd.DataFrame(arcpy.da.TableToNumPyArray(SC, only_relevant_fields))
print "Copied Shape files"


###############################
#Step 5: The Distance function#
###############################

def great_circle_distance(latlong_a, latlong_b):
    """
    This calculates the geodesic distance in km between two pairs of points that have lat and lon
    >>> coord_pairs = [
    ...     # between eighth and 31st and eighth and 30th
    ...     [(40.750307,-73.994819), (40.749641,-73.99527)],
    ...     # sanfran to NYC ~2568 miles
    ...     [(37.784750,-122.421180), (40.714585,-74.007202)],
    ...     # about 10 feet apart
    ...     [(40.714732,-74.008091), (40.714753,-74.008074)],
    ...     # inches apart
    ...     [(40.754850,-73.975560), (40.754851,-73.975561)],
    ... ]
    
    >>> for pair in coord_pairs:
    ...     great_circle_distance(pair[0], pair[1]) # doctest: +ELLIPSIS
    83.325362855055...
    4133342.6554530...
    2.7426970360283...
    0.1396525521278...
    """
    EARTH_CIRCUMFERENCE = 6378.137     # earth circumference in kilometers
    lat1, lon1 = latlong_a
    lat2, lon2 = latlong_b

    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = (math.sin(dLat / 2) * math.sin(dLat / 2) +
            math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
            math.sin(dLon / 2) * math.sin(dLon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    d = EARTH_CIRCUMFERENCE * c
    
    return d

################################################################################################################
#Step 6: The function that creates dictionary where every villages in df1 has a list of closest villages in df2#
################################################################################################################
        
def build_close_towns(df1, df2, radius):
    '''
    Input:
    -two dataframes (df1 and df2) that have unique IDs and coordinates
    -radius - the distance within which to indentify and measure distances for settlements in df1

    Output:
    -a dictionary where every key is a unique ID for the settlements in df1
    
    df1 value example> [20, 45.76102677776362, 22.999048123372233, u'Calanu Mic']
    df2 value example> [1745, 46.933256, 23.271292, 'Frasina']
    '''
    close_towns_dict = {}
    for i in df1.values:
        id_df1, uniqueid_df1, lat_df1, lon_df1, name_df1 = i
        close_towns_dict[id_df1] = {'name' : name_df1,
                      'close_towns_ids' : [],
                      'close_towns_names' : [],
                      'close_towns_dist' : []}
        for j in df2.values:
            id_df2, lat_df2, lon_df2, name_df2= j
            d = great_circle_distance((lat_df1, lon_df1), (lat_df2, lon_df2))
            if d < radius:
                close_towns_dict[id_df1]['close_towns_ids'].append(id_df2)
                close_towns_dict[id_df1]['close_towns_names'].append(name_df2)
                close_towns_dict[id_df1]['close_towns_dist'].append(d)
                
    return close_towns_dict
        
##################################
#Step 7: The fuzzy match function#
##################################

def fuzzy_match_but_only_nearby_towns(df1, df2, close_towns_dict):
    '''
    Input:
    -two dataframes (df1 and df2) that have unique IDs and coordinates
    -a dictionary - close_towns_dict that are within a the radius defined in the previous function

    Output:
    -a CSV file where every settlement in 1956 has the "best" semantically associated match from 1930 from a certain radius
    '''
    MAX_ATTEMPTS = 6
    df1_output = df1.copy()
    village_1930_name = []
    village_1930_name_score = []
    village_1930_ID = []
    village_1930_dist = []
    
    for key1, village_1956 in zip(df1_output.ID_1956.tolist(), df1_output.village_1962_no_diacritics.tolist()):
        #print "Village key", key1
        df1_nearby_cities_names = close_towns_dict[key1]['close_towns_names']
        df1_nearby_cities = close_towns_dict[key1]['close_towns_ids']
        df1_nearby_cities_dist = close_towns_dict[key1]['close_towns_dist']
        df2_filtered = df2.loc[df2.original_order.isin(df1_nearby_cities)] #pay attention if column name changes
        print "Checking village " + village_1956 + " on a list of " +  str(len(df1_nearby_cities)) + " villages from 1930"
        x = process.extract(village_1956, df2_filtered.village_no_diacritics.tolist(), limit=MAX_ATTEMPTS)
        j = 0

        if len(x) == 0 or x[j][1] < 80:
            village_1930_name.append("")
            village_1930_name_score.append("")
            village_1930_ID.append("")
            village_1930_dist.append("")
            
        else:
            while j < len(x):
                #print j, x[j]
                if x[j][0] not in village_1930_name or j == len(x) - 1:
                    break
                else:
                    j += 1

            if j >= len(x) or x[j][1] < 80:
                village_1930_name.append("")
                village_1930_name_score.append("")
                village_1930_ID.append("")
                village_1930_dist.append("")
            else:
                village_1930_name.append(x[j][0])
                village_1930_name_score.append(x[j][1])

                ix = [i for i in range(len(df1_nearby_cities_names)) if df1_nearby_cities_names[i] == x[j][0]][0]
                #print ix
                village_1930_ID.append(df1_nearby_cities[ix])
                village_1930_dist.append(df1_nearby_cities_dist[ix])

    df1_output["village_1930_name"] = village_1930_name
    df1_output["village_1930_name_score"] = village_1930_name_score
    df1_output["village_1930_ID"] = village_1930_ID  
    df1_output["village_1930_dist"] = village_1930_dist
    return df1_output

######################################################
#Step 8: Creating the list of settlements within 15km#
######################################################
close_villages_15km = build_close_towns(villages_1956_df, villages_1930_df, 15)

##################################################
#Step 9: Creating the final CSV file with matches#
##################################################
new = fuzzy_match_but_only_nearby_towns(villages_1956_df, villages_1930_df, close_villages_15km)
new.to_csv(path + "\\Data\\upwork\\razvan\\census_1930_part1\\merged_1956_1930_v2.csv", header=True, index=False, encoding = 'utf8')


