
# Portfolio.Compute()

## Upload a portfolio and compute analytics on it

This code is used to seamlessly upload holdings to create portfolios in the **Investment Portfolio** service, and then quickly calculate a series of analytics on the positions using the **Instrument Analytics** service. 

The primary use case is to use this application for unit testing of all assets in the system to ensure Instrument Analytics is functioning properly.

Ensure that you have a .env file established with the proper credentials to grant this code access to the services (Investment Portfolio, Instrument Analytics) provisioned.

The usage pattern is as follows:

### Step 1: Uploading Holdings

The first step is to upload a file that will be used to create a portfolio or a series of portfolios in the Investment Portfolio service. We use the file format of the Algorithmics Risk Service (ARS) import file as many production clients are already used to that format. You can find an example file in this repo labelled "ICFS_SAMPLE_POSITIONS.csv". 

- The column labeled "UNIQUE ID" must refer to the unique identifier of the asset in our system.
- The "NAME" column will hold the display name of the asset.
- "POSITION UNITS" column holds the quantity.
- "PORTFOLIO" indicates which portfolio the asset belongs to.

The code will create a portfolio for each unique element found in the "PORTFOLIO" column. Future releases of this code will take into account a portfolio hierarchy, but currently each portfolio is entirely independent of each other.

To run this code, use the endpoint **/api/upload** with a POST request with the csv in the above format as the 'file' parameter.

Some notes:
- The portfolio will be loaded as 500-asset chunks as there are currently limitations on POST request sizing. **This means you shouldn't use the 'latest=True'parameter when requesting calculations from the Instrument Analytics service!**
- The portfolio will be tagged as type = 'unit test portfolio' to distinguish between any other portfolios that may exist in the system.

### Step 2: Computing Analytics

Once the portfolio have been loaded, a second API call can be made. This was parsed out as two separate calls as uploading the portfolio may not need to occur frequently, whereas the computations may.

The next step is to call the **/api/unit_test** endpoint. This will perform the following:
- Gather all portfolios in the Investment Portfolio service that are labelled as type = 'unit test portfolio'
- Parse each portfolio into 500-asset chunks to be sent to the Instrument Analytics service (currently a limitation we enforce)
- Compute a series of analytics, which is currently hard-coded to 'THEO/Price' and 'THEO/Value'. This can be changed in the code.
- Return a csv file of results, along with printing out statistics on timing to the console.

Some notes:
- This script currently processes securities in series (synchronously). As the Instrument Analytics service runs on Kubernetes, this script can be enhanced to submit calculation requests asynchronously to improve timing.
- Instruments not found will be ignored.
