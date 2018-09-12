import urllib2
import ConfigParser
try: import simplejson as json
except ImportError: import json
from math import cos, sin, tan, sqrt, pi, radians, degrees, asin, atan2
import matplotlib as mpl
import numpy as np

# define 
flag_miles = True
flag_meters = not flag_miles
miles_to_meters = 1609.34
meters_to_miles = 1./miles_to_meters
r_earth = 3959. if flag_miles else 3959. * meters_to_miles
nautical_miles_to_meters = 1852.

def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]

def sec_to_hms(t):
    t=int(t)
    out=""
    h, m, s = t//3600, (t%3600)//60, (t%3600)%60
    if h > 0: out=out+str(h)+"h"
    if m > 0: out=out+str(m)+"m"
    out += str(s)+"s"
    return out

def flatten(l): return [ el for sublist in l for el in sublist]
def flatten_all(l): return flatten(l[0]) + (flatten(l[1:]) if len(l) > 1 else []) if type(l) is list else [l]

def call_Gmaps_coords_from_address(address, config_file='gmaps_config.cfg', verbose = False):
    """
    Given an address, it returns the [lat,lon] coordinate identified by Google Maps Geocoding API
    """
    # check origin syntax
    if not isinstance(address, str):
        raise Exception('Address should be a string. Check again')
    address_str = address.replace(' ', '+')    
    
    # Get the Google API keys from an external config file
    config = ConfigParser.SafeConfigParser()
    config.read(config_file)
    key = config.get('api', 'api_number')
    
    # set up URL for Geocoding API
    prefix = 'https://maps.googleapis.com/maps/api/geocode/json'
    full_url = '{0}?address={1}&key={2}'.format(prefix, address_str, key)
    #url = urlparse.urlparse('{0}?address={1}&key={2}'.format(prefix, address_str, key))
    #full_url = url.scheme + '://' + url.netloc + url.path + '?' + url.query
    if verbose: print full_url

    # call url and read json
    req = urllib2.Request(full_url)
    f = urllib2.build_opener().open(req)
    d = json.load(f)

    # Parse the json to pull out the geocode
    if not d['status'] == 'OK':
        raise Exception('Error. Google Maps API return status: {}'.format(d['status']))
    res = d['results'][0]['geometry']['location']
    return [res['lat'], res['lng']]
    
    
    
def call_Gmaps_travel_API(origin, dest_list,  config_file='gmaps_config.cfg', verbose = False, extra=''):
    """
    Calls Google Maps Distance Matrix API given an origin and (list of) destination(s).
    Returns lists of travel distances and times.
    """
    # check origin syntax
    if not (isinstance(origin, (list,tuple,np.ndarray)) and len(origin)==2):
        raise Exception('origin should be given as (lat, lon) list or tuple.')
    else: origin_str = ','.join(map(str, origin))

    # check destination syntax
    dest_error_message = 'dest_list should be given as (lat, lon) list or tuple, or list thereof.'
    if isinstance(dest_list, (list,tuple,np.ndarray)):
        if isinstance(dest_list[0], (float,int)) and len(dest_list)==2:
            dest_str = ','.join(map(str, dest_list))
        elif all(map(lambda l: len(l)==2 and isinstance(l[0], (float, int)) , dest_list)): # all elements are latlon pairs
            dest_str = '|'.join([ ','.join(map(str, dest)) for dest in dest_list])
        else:
            raise Exception(dest_error_message)
    else:
        raise Exception(dest_error_message)
    
    # Get the Google API keys from an external config file
    config = ConfigParser.SafeConfigParser()
    config.read(config_file)
    key = config.get('api', 'api_number')
    
    
    # build API URL to query
    
    units = '&units=imperial' if flag_miles else '' # the 'value' distance in the JSON is in meters anyway
    prefix = 'https://maps.googleapis.com/maps/api/distancematrix/json?mode=driving'+units+extra
    full_url = '{0}&origins={1}&destinations={2}&key={3}'.format(prefix, origin_str, dest_str, key)
    if verbose: print full_url
    
    # call url and read json
    req = urllib2.Request(full_url)
    f = urllib2.build_opener().open(req)
    d = json.load(f)

    # Parse the json to pull out the geocode
    times, dists = [], []
    if not d['status'] == 'OK':
        raise Exception('Error. Google Maps API return status: {}'.format(d['status']))
    
    for row in d['rows'][0]['elements']:
        if  row['status'] == 'OK': # all good
            times.append(float(row['duration']['value'])) # make float for easier parsing later on 
            # return distance in miles or km
            dist = row['distance']['value']*(meters_to_miles if flag_miles else 0.001)
            dists.append(dist) 
            
        else: # no route to get there: return very large number
            times.append(1000000.) 
            dists.append(1000000.) 
        
    return times, dists


def move_from_to_xy(p0, dist_x, dist_y):
    """
    Given an origin point p0=(lat,lon), return a (lat,lon) point found moving in the East-West
    and North-South directions by dist_x and dist_y, with distances given in miles/meters.
    Negative inputs correspond to moving South and West.
    """
    lat, lon = p0
    #lat, lon = map(radians, pos0)
    # map distance to degrees. Different for latitude, and longitude. 
    # A nautical mile is 1 minute of longitude at the equator
    # translate all distances to meters
    dist_x, dist_y = map(lambda x: x * miles_to_meters if flag_miles else x, (dist_x, dist_y))
    # displacements in lat,lon degrees
    dlat = dist_y/nautical_miles_to_meters/60.
    dlon = dist_x/nautical_miles_to_meters/60./cos(radians(lat))
    return [ lat+dlat, lon+dlon ]

def move_from_to_angle(p0, dist_r, alpha):
    """
    Given an origin point p0=(lat,lon), return a (lat,lon) point found moving in the direction defined
    by the bearing alpha (in radians, angle between N and direction), with radial distance given in miles/meters.
    """

    lat1, lon1 = map(radians, p0)
    # displacements in lat,lon
    lat2 = asin( sin(lat1) * cos(dist_r / r_earth) + cos(lat1) * sin(dist_r / r_earth) * cos(alpha) )
    lon2 = lon1 + atan2( sin(alpha) * sin(dist_r / r_earth) * cos(lat1), cos(dist_r / r_earth) - sin(lat1) * sin(lat2))
    return map(degrees, [ lat2, lon2 ])



def make_xy_grid(p0, max_time, nx, ny, max_speed = 70.):
    """
    Make a rectangular grid centered around point p0=(lat,lon), up to a distance given by 
    (max_time*max_speed) on each side, with nx, ny points in East-West, North-South directions 
    (x=longitude, y=latitude). If max_time = (tx, ty), define different distances in the x,y axes.
    If nx or ny are a pair (e.g. nx=(n1,n2)), define a non-centered grid, i.e. interpret the
    two numbers as number of points in the negative, positive axis direction.
    """
    dist_x, dist_y = map(lambda x: x*max_speed, max_time if isinstance(max_time, (list,tuple,np.ndarray)) else (max_time, max_time))
    if all(map(lambda n: isinstance(n, int), (nx,ny) )):
        grid = [ move_from_to_xy(p0, dx, dy) for dx in np.linspace(-dist_x, dist_x, nx)  for dy in np.linspace(-dist_y, dist_y, ny) ]
    elif all(map(lambda n: isinstance(n, (list,tuple,np.ndarray)) and len(n)==2, (nx,ny) )):
        xlow = -2. * dist_x * (1.*nx[0]/sum(nx))
        xhigh = xlow + 2. * dist_x 
        ylow = -2. * dist_y * (1.*ny[0]/sum(ny))
        yhigh = ylow + 2. * dist_y
        grid = [ move_from_to_xy(p0, dx, dy) for dx in np.linspace(xlow, xhigh, sum(nx))  for dy in np.linspace(ylow, yhigh, sum(ny)) ]
    return grid
        
        
def make_polar_grid(p0, max_time, n_radial, n_angles, max_speed = 70):
    """
    Make a polar grid centered around point p0=(lat,lon), up to a radial distance given by 
    (max_time*max_speed) in n_radial steps, along n_angles directions dividing equally the 
    full circle. If n_angles = (alpha0, alpha1, n), only draw a cone in between alpha0 and
    alplha1, divided n times
    """
    
    dist_r = max_time*max_speed
    grid = [list(p0)]
    if isinstance(n_angles, int):
        grid += [ move_from_to_angle(p0, dr, da) for dr in np.arange(0, dist_r, dist_r/(n_radial+1))[1:]  for da in np.linspace(0, 2*pi, n_angles+1)[:-1] ] # do not repeat 2pi==0
    elif isinstance(n_angles, (list,tuple,np.ndarray)) and len(n_angles)==3:
        a0, a1, n_a = n_angles
        grid += [ move_from_to_angle(p0, dr, da) for dr in np.arange(0, dist_r, dist_r/(n_radial+1.))[1:]  for da in np.linspace(a0, a1, n_a) ]
    return grid
        

def make_mixed_grid(p0, max_time, n_radial, n_angles, nx, ny, max_speed = 70.):
    """
    Build a mixed polar/rectangular grid around p0, up to distance (max_time*max_speed),
    with polar grid parameters n_radial, n_angles and rectangular parameters nx, ny.
    """
    grid_r = make_polar_grid(p0, max_time, n_radial, n_angles, max_speed)
    grid_xy = make_xy_grid(p0, max_time, nx, ny, max_speed)
    return grid_r+grid_xy

def run_travel_grid(p0, grid):
    """
    Calls Google Maps Distance Matrix API to find distance between p0=(lat,lon) and each of the
    grid points in grid. Returns grid, times (in seconds), distances (in miles/km).
    """
    # free API rate limits: no more than 25 destinations per call
    grid_chunks = chunks(grid, 25)
    grid0, times, dists = [], [], []
    for dest_list in grid_chunks:
        grid0.append(dest_list)
        tt, dd = call_Gmaps_travel_API(p0, dest_list)
        times.append(tt)
        dists.append(dd)
    
    return flatten(grid0), flatten(times), flatten(dists)


def get_bearing(p1,p2):
    lat1, lon1 = map(radians, p1)
    lat2, lon2 = map(radians, p2)
    y = cos(lat2) * sin(lon1-lon2)
    x = cos(lat1)*sin(lat2) -cos(lat2)*sin(lat1)*cos(lon1-lon2)
    return atan2(y,x)

        
def get_distance(p1,p2):
    lat1, lon1 = map(radians, p1)
    lat2, lon2 = map(radians, p2)
    h = sin((lat1-lat2)/2.)**2+cos(lat1)*cos(lat2)*sin((lon1-lon2)/2.)**2
    d=2. * r_earth * asin(np.sqrt(h))
    return d


def smoothen2d(x, y, z, N_nearest=9):
    """
    Given a 2D grid (x,y) with values z on the grid, for each point average over the
    closest N_nearest points and return that value at that point. Iterate over whole grid.
    """
    x,y,z = map(np.array,[x,y,z])
    result = []
    for vec in zip(x,y,z):
        closest = np.argsort((vec[0]-x)**2+(vec[1]-y)**2)[:N_nearest]
        result.append([vec[0],vec[1],np.mean(np.array(z)[closest])])
    return zip(*result)


def lighten_color(color, amount=0.5):
    """ Source: https://gist.github.com/ihincks/6a420b599f43fcd7dbd79d56798c4e5a
    Lightens the given color by multiplying (1-luminosity) by the given amount.
    Input can be matplotlib color string, hex string, or RGB tuple.

    Examples:
    >> lighten_color('g', 0.3)
    >> lighten_color('#F034A3', 0.6)
    >> lighten_color((.3,.55,.1), 0.5)
    """
    import colorsys
    try:
        c = mpl.colors.cnames[color]
    except:
        c = color
    c = colorsys.rgb_to_hls(*mpl.colors.to_rgb(c))
    return colorsys.hls_to_rgb(c[0], 1 - amount * (1 - c[1]), c[2])




        