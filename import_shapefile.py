import shapefile
import pprint
from geomet import wkt
import pprint
from sqlalchemy.sql import text
from sqlalchemy import create_engine
from configobj import ConfigObj

config = ConfigObj(".env")
database_uri = "mysql+mysqldb://%(database_user)s:%(database_password)s@%(database_host)s/%(database_name)s" % config
engine = create_engine(database_uri)
connection = engine.connect()
connection.execute(text("delete from routes"))

sf = shapefile.Reader("Solid_Waste_Collection_Calendar-shp/Solid_Waste_Collection_Calendar.shp")

day_number = {'MONDAY': 0, 'TUESDAY': 1, 'WEDNESDAY': 2, 'THURSDAY': 3, 'FRIDAY': 4, 'SATURDAY': 5, 'SUNDAY': 6}

records = sf.records()
i = 0
pp = pprint.PrettyPrinter(indent=4)

for r in records:
  pp.pprint(r)
  pickup_day = day_number[r[1]]
  schedule = r[3]
  shape = sf.shapeRecord(i).shape
  areastr = wkt.dumps(shape.__geo_interface__)
  connection.execute(text("insert into routes (pickup_day, schedule, area, areastr) values (:pickup_day, :schedule, ST_GeomFromText(:areastr), :areastr)").bindparams(pickup_day=pickup_day, schedule=schedule, areastr=areastr))
  i += 1
