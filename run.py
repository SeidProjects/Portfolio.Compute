# Written by Rob Seidman on 10/03/2017
from flask import Flask, render_template, jsonify, json, url_for, request, redirect, Response, flash, abort, make_response
import requests
import StringIO
import io
import os
import csv
import datetime
import investmentportfolio
import instrumentanalytics

print ('Running portfolio.upload.py')
app = Flask(__name__)

# On Bluemix, get the port number from the environment variable VCAP_APP_PORT
# When running this app on the local machine, default the port to 8080
port = int(os.getenv('VCAP_APP_PORT', 8080))
host='0.0.0.0'

# I couldn't add the services to this instance of the app so VCAP is empty
# do this to workaround for now
if 'VCAP_SERVICES' in os.environ:
    if str(os.environ['VCAP_SERVICES']) == '{}':
        print ('Using a file to populate VCAP_SERVICES')
        with open('VCAP.json') as data_file:
            data = json.load(data_file)
        os.environ['VCAP_SERVICES'] = json.dumps(data)

#======================================RUN LOCAL======================================
# stuff for running locally
if 'RUN_LOCAL' in os.environ:
    print ('Running locally')
    port = int(os.getenv('SERVER_PORT', '5555'))
    host = os.getenv('SERVER_HOST', 'localhost')
    with open('VCAP.json') as data_file:
        data = json.load(data_file)
    os.environ['VCAP_SERVICES'] = json.dumps(data)

#======================================MAIN PAGES======================================
@app.route('/')
def run():
    return "Portfolio.Upload running on port " + str(port) + "."

@app.route('/api/upload', methods=['POST'])
def portfolio_from_csv():
    """
    Loads a portfolio in Algo Risk Service (ARS) format into the Investment Portfolio service.
    """
    holdings = {
        'timestamp':'{:%Y-%m-%dT%H:%M:%S.%fZ}'.format(datetime.datetime.now()),
        'holdings':[]
    }
    #Check to see if a file was sent
    if len(request.files.keys()) == 0:
        print("No file posted. Returning.")
        return "No file posted."
    
    #read file
    p_file = request.files['file']
    stream = io.StringIO(p_file.stream.read().decode("UTF8"), newline=None)
    reader = csv.reader(stream,delimiter=',')
    data = [row for row in reader]
    p_file.close()
    headers = [row for row in data[0]]

    #Loop through and segregate each portfolio by its identifier (there may be multiple in the file)
    #Column 1 (not 0) is the ID column. Column 5 is the PORTFOLIO column...
    portfolios = {}
    unique_id_col =  headers.index("UNIQUE ID")
    id_type_col =  headers.index("ID TYPE")
    name_col =  headers.index("NAME")
    pos_units_col =  headers.index("POSITION UNITS")
    portfolio_col =  headers.index("PORTFOLIO")
    price_col =  headers.index("PRICE")
    currency_col =  headers.index("CURRENCY")

    #for d in data...
    for d in data[1:]:
        if d[portfolio_col] not in portfolios:
            portfolios[d[portfolio_col]] = [{
                "name":d[name_col],
                "instrumentId":d[unique_id_col],
                "quantity":d[pos_units_col]
            }]
        else:
            portfolios[d[5]].append({
                "name":d[name_col],
                "instrumentId":d[unique_id_col],
                "quantity":d[pos_units_col]
            })
    
    #Send each portfolio and its holdings to the investment portfolio service
    for key, value in portfolios.iteritems():
        my_portfolio = {
            "timestamp": '{:%Y-%m-%dT%H:%M:%S.%fZ}'.format(datetime.datetime.now()) ,
            'closed':False,
            'data':{'type':'unit test portfolio'},
            'name':key
        }
        
        #create portfolio
        try:
            req  = investmentportfolio.Create_Portfolio(my_portfolio)
        except:
            print("Unable to create portfolio for " + str(key) + ".")
        
        try:
            for h in range(0,len(value),500):
                hldgs = value[h:h+500]
                req  = investmentportfolio.Create_Portfolio_Holdings(str(key),hldgs)
        except:
            print("Unable to create portfolio holdings for " + str(key) + ".")
    return "Successfully attempted to create all portfolios."


#Returns list of 'unit test' portfolios
@app.route('/unit_test_portfolios',methods=['GET'])
def get_unit_test_portfolios():
    '''
    Returns the available user portfolio names in the Investment Portfolio service.
    Uses type='user_portfolio' to specify.
    '''
    names = []
    res = investmentportfolio.Get_Portfolios_by_Selector('type','unit test portfolio')
    try:
        for a in res['portfolios']:  
            names.append(a['name'])
        #Gather only unique names, as there's likely history for the benchmarks.
        names = list(set(names))
        return names
    except:
        return names

#Deletes all unit test holdings and portfolios for cleanup
@app.route('/api/unit_test_delete',methods=['GET'])
def get_unit_test_delete():
    '''
    Deletes all portfolios and respective holdings that are of type 'unit test'
    '''
    portfolios = investmentportfolio.Get_Portfolios_by_Selector('type','unit test portfolio')['portfolios']
    print(portfolios)
    for p in portfolios:
        holdings = investmentportfolio.Get_Portfolio_Holdings(p['name'],False)
        # delete all holdings
        for h in holdings['holdings']:
            timestamp = h['timestamp']
            rev = h['_rev']
            investmentportfolio.Delete_Portfolio_Holdings(p['name'],timestamp,rev)
        investmentportfolio.Delete_Portfolio(p['name'],p['timestamp'],p['_rev']) 
    return "Portfolios deleted successfully."

#Calculates unit tests for a list of portfolios
@app.route('/api/unit_test',methods=['GET'])
def compute_unit_tests(portfolios=None):
    '''
    Iterates through all portfolios with type='unit test' to 
    compute analytics from Instrument Analytics service.
    Analytics are specified in a config file.
    '''
    #Stopwatch
    start_time = datetime.datetime.now()

    #Grab all unit test portfolios if specific portfolio names not supplied.
    if not portfolios:
        portfolios = get_unit_test_portfolios()

    analytics = ['THEO/Price','THEO/Value']
    results = [['Portfolio','Unique ID'] + analytics + ['Date']]
    
    for p in portfolios:
        portfolio_start = datetime.datetime.now()
        holdings = investmentportfolio.Get_Portfolio_Holdings(p,False)['holdings']
        #Since the payload is too large, odds are there are 500-instrument chunks added to the portfolio.
        for ph in range(0,len(holdings)):
            instruments = [row['instrumentId'] for row in holdings[ph]['holdings']]
            print("Processing " + str(p) + " portfolio segment #"+str(ph) +".")
            #send 500 IDs at a time to Instrument Analytics Service:
            #for i in instruments...
            for i in range(0,len(instruments),500):
                ids = instruments[i:i+500]
                ia = instrumentanalytics.Compute_InstrumentAnalytics(ids,analytics)

                #for j in results...
                if 'error' not in ia:
                    for j in ia:
                        r = [p,j['instrument']] 
                        for a in analytics:
                            r.append(j['values'][0][a])
                        r.append(j['values'][0]['date'])
                        results.append(r)
                #Debug
                if i+500<len(instruments):
                    l = i+500
                else:
                    l = len(instruments)
                print("Processed securities " + str(i) + " through " + str(l) + ". Process length: " + str(datetime.datetime.now() - portfolio_start))

    si = StringIO.StringIO()
    cw = csv.writer(si)
    cw.writerows(results)
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=IA_unittest.csv"
    output.headers["Content-type"] = "text/csv"
    print("Unit testing completed. Total time elapsed: " + str(datetime.datetime.now() - start_time))
    return output

    #return Response(results, mimetype='text/csv')

if __name__ == '__main__':
    app.run(host=host, port=port)