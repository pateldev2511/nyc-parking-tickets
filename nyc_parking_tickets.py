# -*- coding: utf-8 -*-
"""NYC_Parking_Tickets.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1_UaNOgDms4x5p-jM2YyZrhPt8HMnlw6V

# Setup
"""

!apt-get install openjdk-8-jdk-headless -qq > /dev/null
!wget -q https://archive.apache.org/dist/spark/spark-3.2.1/spark-3.2.1-bin-hadoop3.2.tgz
!tar xf spark-3.2.1-bin-hadoop3.2.tgz
!pip install -q findspark
!pip install plotly
!pip install pyarrow

import os
os.environ["JAVA_HOME"] = "/usr/lib/jvm/java-8-openjdk-amd64"
os.environ["SPARK_HOME"] = "/content/spark-3.2.1-bin-hadoop3.2"
import findspark
findspark.init()

import numpy as np # linear algebra
import pandas as pd # data processing, CSV file I/O (e.g. pd.read_csv)
import matplotlib.pyplot as plt
import seaborn as sns
import sklearn
import random
import os
import plotly.express as px
import json

from pyspark.sql import SparkSession 
from pyspark.ml  import Pipeline     
from pyspark.sql import SQLContext  
from pyspark.sql.functions import regexp_replace
from pyspark.sql.functions import mean,col,split, col, regexp_extract, when, lit, sum
from pyspark.ml.feature import StringIndexer, VectorAssembler
from pyspark.ml.evaluation import MulticlassClassificationEvaluator
from pyspark.ml.feature import QuantileDiscretizer

# Connect to the drive.
from google.colab import drive
drive.mount('/content/drive')

# Create SparkSession
spark = SparkSession.builder.appName('ParkingTickets').getOrCreate()
sc = spark.sparkContext
spark.conf.set("spark.sql.execution.arrow.enabled", "true")

# Load the file. Dataset: https://data.cityofnewyork.us/City-Government/Parking-Violations-Issued-Fiscal-Year-2020/p7t3-5i9s/data
filepath = "/content/drive/MyDrive/NycParkingTickets/Parking_Violations_Issued_-_Fiscal_Year_2020.csv"
filepath_violation_des = "/content/drive/MyDrive/NycParkingTickets/ParkingViolationCodes_January2020.csv"
nyc_map_filepath = "/content/drive/MyDrive/NycParkingTickets/PolicePrecincts.geojson"

dataset = spark.read.csv(filepath, inferSchema=True, header=True)
dataset_vd = spark.read.csv(filepath_violation_des, inferSchema=True, header=True)

# Dataset Analysis
dataset.printSchema()

"""# Violations by the precinct locations"""

# Violations by Precinct in 2021
violation_precinct = "Violation Precinct"
violation_by_precinct = dataset.groupBy(violation_precinct).count().orderBy("count", ascending=False)
violation_by_precinct.show()

# Since there is no precinct 0, we need to remove it.
violation_by_precinct = violation_by_precinct.filter(violation_by_precinct[violation_precinct] != "0")
violation_by_precinct.show()

nyc_map_file = open(nyc_map_filepath)
nyc_map_json = json.load(nyc_map_file)
vbp = violation_by_precinct.toPandas()

fig = px.choropleth(vbp, geojson=nyc_map_json, color="count",
                    locations="Violation Precinct", featureidkey="properties.precinct",
                    # color_continuous_scale="Viridis",
                    color_continuous_scale="Reds",
                    projection="mercator"
                   )
fig.update_geos(fitbounds="locations", visible=False)
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, height=700)
fig.show()

"""# Violations types"""

violation_code = "Violation Code"
violation_description = "VIOLATION DESCRIPTION"
violation_by_code = dataset.groupBy(violation_code).count().orderBy("count", ascending=False)
# Since violation is coded, a merge is required to make violation code human readable
violation_by_code = violation_by_code.join(dataset_vd, dataset_vd[violation_code] == violation_by_code[violation_code])\
.select(dataset_vd[violation_description], violation_by_code["count"], violation_by_code[violation_code]).orderBy(violation_description)
violation_by_code.show(100)

# We need to merge similiar kind of tickets into the similar violation description
violation_by_code = violation_by_code.withColumn(violation_description, 
                                                 when(col(violation_description).contains("NO PARKING"), "NO PARKING")
                                                 .otherwise(col(violation_description))).orderBy(violation_description)
violation_by_code = violation_by_code.withColumn(violation_description, 
                                                 when(col(violation_description).contains("NO STANDING") | 
                                                      col(violation_description).contains("NO STD") | 
                                                      col(violation_description).contains("NO STOP")| 
                                                      col(violation_description).contains("NO STAND"), "NO STANDING")
                                                 .otherwise(col(violation_description))).orderBy(violation_description)
violation_by_code = violation_by_code.withColumn(violation_description, 
                                                 when(col(violation_description).contains("FAIL TO DISP") | 
                                                      col(violation_description).contains("FAILURE TO DISP") | 
                                                      col(violation_description).contains("FAIL TO DSPLY"), "FAIL TO DISPLAY RECIPT")
                                                 .otherwise(col(violation_description))).orderBy(violation_description)
violation_by_code = violation_by_code.withColumn(violation_description, 
                                                 when(col(violation_description).contains("EXPIRED METER") | 
                                                      col(violation_description).contains("EXPIRED MUNI"), "EXPIRED METER")
                                                 .otherwise(col(violation_description))).orderBy(violation_description)
violation_by_code = violation_by_code.withColumn(violation_description, 
                                                 when(col(violation_description).contains("DOUBLE PARKING"), "DOUBLE PARKING")
                                                 .otherwise(col(violation_description))).orderBy(violation_description)
violation_by_code = violation_by_code.withColumn(violation_description, 
                                                 when(col(violation_description).contains("REG. STICKER") | 
                                                      col(violation_description).contains("REG STICKER"), "EXPIRED REGISTRATION")
                                                 .otherwise(col(violation_description))).orderBy(violation_description)
violation_by_code = violation_by_code.withColumn(violation_description, 
                                                 when(col(violation_description).contains("INSP. STICKER") | 
                                                      col(violation_description).contains("INSP STICKER"), "EXPIRED INSPECTION")
                                                 .otherwise(col(violation_description))).orderBy(violation_description)
violation_by_code.show(100)

# We need to merge all the parking tickets
violation_by_code = violation_by_code.groupBy(violation_description).agg(sum("count").alias("count")).orderBy("count", ascending=False)
vbc = violation_by_code.toPandas()
violation_by_code.show(100)

# Plot the graph
vbc.plot.barh(x='VIOLATION DESCRIPTION', y='count', rot=0, figsize=(25, 20))

"""# Violation by time"""

# Group by the time to see what time values we have
violation_time = "Violation Time"
violation_by_time = dataset.groupBy(violation_time).count().orderBy("count", ascending=False)
violation_by_time.show(20)

# Let's convert AM & PM to 24 hour date format. 
# Also remove minutes because we only want to analyze on the hours and not minutes
re0 = '\A00\d{2}A$'
re1 = '\A01\d{2}A$'
re2 = '\A02\d{2}A$'
re3 = '\A03\d{2}A$'
re4 = '\A04\d{2}A$'
re5 = '\A05\d{2}A$'
re6 = '\A06\d{2}A$'
re7 = '\A07\d{2}A$'
re8 = '\A08\d{2}A$'
re9 = '\A09\d{2}A$'
re10 = '\A10\d{2}A$'
re11 = '\A11\d{2}A$'
re25 = '\A12\d{2}A$'
re12 = '\A12\d{2}P$'
re13 = '\A01\d{2}P$'
re14 = '\A02\d{2}P$'
re15 = '\A03\d{2}P$'
re16 = '\A04\d{2}P$'
re17 = '\A05\d{2}P$'
re18 = '\A06\d{2}P$'
re19 = '\A07\d{2}P$'
re20 = '\A08\d{2}P$'
re21 = '\A09\d{2}P$'
re22 = '\A10\d{2}P$'
re23 = '\A11\d{2}P$'
re24 = '\A00\d{2}P$'
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re0,'00'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re25,'00'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re1,'01'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re2,'02'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re3,'03'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re4,'04'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re5,'05'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re6,'06'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re7,'07'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re8,'08'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re9,'09'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re10,'10'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re11,'11'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re12,'12'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re13,'13'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re14,'14'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re15,'15'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re16,'16'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re17,'17'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re18,'18'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re19,'19'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re20,'20'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re21,'21'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re22,'22'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re23,'23'))
violation_by_time = violation_by_time.withColumn(violation_time, regexp_replace("Violation Time",re24,'00'))
violation_by_time.show()

# Merge the same hour value as not we have normalized data
violation_by_time = violation_by_time.groupBy(violation_time).agg(sum("count").alias("count")).orderBy(violation_time)
violation_by_time.show(200)

# Let's see how many unique time we have. We should only have 24.
violation_by_time.count()

# Since the number of unique value is small and count of each unique value
# is small, we can filter the only value.
hours = {"00","01","02","03","04","05","06","07","08","09","10","11","12","13","14","15","16","17","18","19","20","21","22","23","24"}
violation_by_time = violation_by_time.filter(violation_by_time[violation_time].isin(hours)) 
vbt = violation_by_time.toPandas()
vbt.head(25)

# Plot the graph
vbt.plot.bar(x='Violation Time', y='count', rot=0, figsize=(20,5))

"""# Violation by car model"""

vehicle_make = "Vehicle Make"
violation_by_vehicle_make = dataset.groupBy(vehicle_make).count().orderBy("count", ascending=False)
violation_by_vehicle_make.show()

# Since there is Most of the data is on valid with lower count values , we need to remove it.
violation_by_vehicle_make = violation_by_vehicle_make.filter(col("count") >= 1000 )
violation_by_vehicle_make = violation_by_vehicle_make.filter(col("Vehicle Make") != 'null' )
violation_by_vehicle_make.show(100)

#As there are data for same Vehical maker with different case type, we need to merge. Below have done for some vehical makers
violation_by_vehicle_make = violation_by_vehicle_make.withColumn(vehicle_make, regexp_replace(vehicle_make,'(?i)toyot','TOYOTA'))
violation_by_vehicle_make = violation_by_vehicle_make.withColumn(vehicle_make, regexp_replace(vehicle_make,'(?i)ford','FORD'))
violation_by_vehicle_make = violation_by_vehicle_make.withColumn(vehicle_make, regexp_replace(vehicle_make,'(?i)honda','HONDA'))
violation_by_vehicle_make = violation_by_vehicle_make.withColumn(vehicle_make, regexp_replace(vehicle_make,'(?i)bmw','BMW'))
violation_by_vehicle_make = violation_by_vehicle_make.withColumn(vehicle_make, regexp_replace(vehicle_make,'(?i)jeep','JEEP'))
violation_by_vehicle_make = violation_by_vehicle_make.withColumn(vehicle_make, regexp_replace(vehicle_make,'(?i)hyun|hyund' ,'HUNDAI'))
violation_by_vehicle_make.show(100)

violation_by_vehicle_make = violation_by_vehicle_make.groupBy(vehicle_make).agg(sum("count").alias("count")).orderBy("count", ascending=False)
vbvm = violation_by_vehicle_make.toPandas()
violation_by_vehicle_make.show(100)

colors = list('rgbkm')
vbvm.plot.barh(x='Vehicle Make', y='count', rot=0, figsize=(30, 50), color=colors)

"""# Violation by street"""

# Grouping by street name to figure out kind of values.
street_name = "Street Name"
violation_by_street_name = dataset.groupBy(street_name).count().orderBy("count", ascending=True)
violation_by_street_name.show(100)

# Filtering out only busy stree to avoid street with minor violation and
# false street names.
violation_by_street_name = violation_by_street_name.withColumnRenamed("count","n")
violation_by_street_name = violation_by_street_name.filter("n >= 10000")
violation_by_street_name.show(100)

# Converting to pandas to plot.
vbs = violation_by_street_name.toPandas()

# Plot the findings.
vbs.plot.barh(x=street_name , y='n', rot=0, figsize=(30,70))