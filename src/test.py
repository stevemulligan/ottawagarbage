from pyproj import Proj, transform

outProj = Proj(init='epsg:2951')
inProj = Proj(init='epsg:4326')
x2,y2 = transform(inProj,outProj,-75.8847524,45.2863783)
print("new points",x2,y2)

