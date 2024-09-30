"""Streamlit app to simulate investments over a period of time in the past"""

import datetime
import pandas as pd
import streamlit as st
import yfinance as yf
from currency_converter import CurrencyConverter
from dateutil.relativedelta import relativedelta
import helper

st.set_page_config(layout='wide')
st.title('Investing Simulator')
st.write(
    '''
    - This app allows you to simulate how your investments would have developed 
    over time if you had invested periodically in the past.

    - The simulation assumes that it is possible to buy fractional shares
    and that there are no currency exchange fees. Note that some currency 
    exchange rates might be [missing](https://pypi.org/project/CurrencyConverter/).

    - If the periodic investment happens to be on a day when the market is closed,
    the buy order will be executed in the next market opening.
    '''
)

today = datetime.datetime.now()
curr_conv = CurrencyConverter(
    fallback_on_missing_rate=True,
    fallback_on_wrong_date=True
)
currencies = sorted(curr_conv.currencies)

st.header('Choose your investment strategy')
# Ask user to decide investment date range, as well as frequency and amount for investing
with st.form('input_investment_parameters'):

    col_input_1, col_input_2, col_input_3, col_input_4 = st.columns(4)

    with col_input_1:
        date_start, date_end = st.date_input(
            label='In what date range will you be investing?',
            value=(datetime.date(day=1, month=1, year=today.year), today),
            min_value=datetime.date(day=1, month=1, year=1970),
            max_value=today,
            format='DD/MM/YYYY'
        )

    with col_input_2:
        investment_day = st.selectbox(
            label='On what day of the month will you invest?',
            options=range(1,29),
            index=0,
            help='Make sure there is at least one investment day in the selected date range.'
        )

    with col_input_3:
        investment_amount = st.number_input(
            label='How much will you invest periodically?',
            min_value=1,
            value=100,
            step=50
        )

    with col_input_4:
        base_currency = st.selectbox(
            label='Select your base currency.',
            options=currencies,
            index=currencies.index('USD')
        )

    input_ticker_symbol = st.text_input(
        label='Enter the ticker symbol(s) of your investment choice (separated by commas)',
        help='''
        A ticker symbol or stock symbol is an abbreviation used to uniquely identify publicly 
        traded shares of a particular stock or security on a particular stock exchange. 
        You can find these symbols at [YahooFinance](https://finance.yahoo.com/quote/AAPL/). 

        (Examples) Symbol - Company:

        AAPL - Apple, Inc.

        MSFT - Microsoft Corporation

        TSLA - Tesla, Inc. 
        ''',
        placeholder='Example: AAPL, MSFT, TSLA'
    )

    submitted = st.form_submit_button(label='CONFIRM CHOICES', use_container_width=True)
    if 'submitted' not in st.session_state:
        st.session_state['submitted'] = submitted

if st.session_state['submitted']:

    # Find correct start date
    is_date_correct, current_investment_date = helper.is_investment_day_valid(
        investment_day=investment_day,
        date_start=date_start,
        date_end=date_end
    )

    # If periodic investment day is not within the date range
    if not is_date_correct:
        st.write('Please select a periodic investment day within the date range.')
        st.write(
            f'''
            The periodic investment day ({investment_day}) is outside of the
            date range {date_start:%B} {date_start.day}-{date_end.day}
            '''
        )

    # If user has not entered any ticker symbols
    elif input_ticker_symbol == '':
        st.write('Please enter at least one ticker symbol.')

    # If user has valid investment day and entered a symbol
    else:

        tickers = {}                # Store yf.Ticker objects
        symbols = []                # Store symbols
        securities_invested = []    # Store security names

        # Remove whitespaces and separate by commas
        ticker_symbols = input_ticker_symbol.replace(' ', '').split(',')
        # Remove duplicates and sort alphabetically
        ticker_symbols = set(ticker_symbols)

        for ts in ticker_symbols:
            ticker = yf.Ticker(ts)

            # If symbol does not exist, ticker.info returns a dictionary of length 1
            if len(ticker.info) == 1:
                st.write(f'The ticker symbol {ts} was not found.')
            # If symbol does exist
            else:
                symbol = ticker.info['symbol']

                # Try to get security long name, otherwise short name, otherwise symbol
                try:
                    security_name = f'{ticker.info['longName']} ({symbol})'
                except KeyError:
                    try:
                        security_name = f'{ticker.info['shortName']} ({symbol})'
                    except KeyError:
                        security_name = symbol

                # Store security info
                if symbol not in tickers:
                    tickers[symbol] = ticker

                symbols.append(symbol)
                securities_invested.append(security_name)

        NUM_SECURITIES_INVESTED = len(securities_invested)
        if NUM_SECURITIES_INVESTED == 0:
            st.write(
                'Sorry, no data was found for the symbols you entered. Make sure they are correct.'
            )
        else:

            # Create pandas DataFrame with info about each buy order
            # Columns: Investment date, symbol, amount of shares bought, buy price
            rows = []   # Build DataFrame with list of lists (each list is a row)

            # Store historical security prices
            if 'dfs_securities' not in st.session_state:
                st.session_state['dfs_securities'] = {}

            INVESTMENT_EXISTS = False
            symbols = sorted(symbols)
            # Get the buy price for each investment date and symbol
            while current_investment_date <= date_end:
                for symbol in symbols:
                    if symbol not in st.session_state['dfs_securities']:
                        df_security = yf.download(
                            tickers=symbol,
                            start=date_start,
                            end=today,
                            actions=True,
                            rounding=True
                        )

                        st.session_state['dfs_securities'][symbol] = df_security

                    df_investments_symbol = st.session_state['dfs_securities'][symbol].copy()

                    is_data_found_for_symbol = len(df_investments_symbol) != 0
                    # If no data was found for symbol
                    if not is_data_found_for_symbol:
                        st.write(
                            f'''
                            Unfortunately no price data was found for {symbol} from
                            {date_start:%B %d %Y} until {today:%B %d %Y}.
                            '''
                        )

                    # If data was found for symbol
                    if is_data_found_for_symbol:
                        # Create row for DataFrame
                        row = []

                        market_open_dates = df_investments_symbol.index.date
                        # If market is open, buy on investment date
                        if current_investment_date in market_open_dates:
                            buy_price_original = df_investments_symbol.loc[
                                market_open_dates == current_investment_date,
                                'Open'
                            ].iloc[0]

                            actual_investment_date = current_investment_date
                            INVESTMENT_EXISTS = True

                            # st.write(
                            #     f'''
                            #     {symbol}
                            #     - Scheduled day: {current_investment_date}
                            #     - Actual investment date: {actual_investment_date}
                            #     '''
                            # )

                        # If market is closed, buy at next market open
                        if current_investment_date not in market_open_dates:
                            is_future_date = market_open_dates > current_investment_date
                            # If market has not opened yet in the future, break
                            if is_future_date.sum() == 0:
                                st.write(
                                    f'''
                                    No market data was found for {symbol} scheduled investment on
                                    {current_investment_date} or the following market open.
                                    '''
                                )
                                break

                            future_dates = df_investments_symbol.loc[is_future_date]
                            next_market_open = future_dates.reset_index().iloc[0]
                            buy_price_original = next_market_open['Open']
                            actual_investment_date = next_market_open['Date'].date()
                            INVESTMENT_EXISTS = True

                            # st.write(
                            #     f'''
                            #     {symbol}
                            #     - Scheduled day: {current_investment_date}
                            #     - Actual investment date: {actual_investment_date}
                            #     '''
                            # )

                    # Convert buy price from security's currency to base currency
                    currency_security = tickers[symbol].info['currency']
                    if currency_security == base_currency:
                        buy_price_converted = buy_price_original
                    else:
                        buy_price_converted = curr_conv.convert(
                            amount=buy_price_original,
                            currency=currency_security,
                            new_currency=base_currency,
                            date=actual_investment_date,
                        )

                    # Allow for fractional shares if buy price is bigger
                    num_shares_bought = investment_amount / buy_price_converted

                    # Add DataFrame row elements
                    row.append(actual_investment_date)
                    row.append(symbol)
                    row.append(tickers[symbol].info['quoteType'])
                    row.append(currency_security)
                    row.append(num_shares_bought)
                    row.append(buy_price_original)
                    row.append(buy_price_converted)
                    row.append(investment_amount)
                    rows.append(row)

                # Once the investment date is covered for both symbols,
                # move on to next month
                current_investment_date += relativedelta(months=1)

            # If unable to execute any buy orders
            if not INVESTMENT_EXISTS:
                st.write(
                    f'''
                    There was no data retrieved for any investments on your investment day 
                    ({investment_day}) between the selected start and end dates. Perhaps try
                    a different investment day.
                    '''
                )

            # If able to execute at least 1 buy order
            if INVESTMENT_EXISTS:
                st.write(
                    f'''
                    You will invest in the following {NUM_SECURITIES_INVESTED}
                    {'security' if NUM_SECURITIES_INVESTED == 1 else 'securities'}
                    on day {investment_day} of each month from
                    {date_start:%B %d (%Y)} until {date_end:%B %d (%Y)}:
                    '''
                )

                # Write out the different securities to invest in
                NUM_COLS = 4
                cols_securities = st.columns(NUM_COLS)
                for i, security in enumerate(sorted(securities_invested)):
                    with cols_securities[i%NUM_COLS]:
                        st.write(f'{i+1}. {security}')

                # Create monthly investments DataFrame from rows
                df_investments = pd.DataFrame(
                    data=rows,
                    columns=[
                        'Purchase Date',
                        'Symbol',
                        'Security Type',
                        'Original Currency',
                        'Shares Bought', 
                        'Share Price at Purchase (Original Currency)',
                        f'Share Price at Purchase ({base_currency})',
                        f'Invested Capital ({base_currency})'
                    ]
                )

                # Convert to datetime.date
                df_investments['Purchase Date'] = pd.to_datetime(df_investments['Purchase Date'])
                df_investments['Purchase Date'] = df_investments['Purchase Date'].dt.date

                st.header('Transactions')
                st.write('Your periodic investments are shown below.')
                st.dataframe(df_investments, use_container_width=True)

                # Find current investment value

                # Match values from dictionary to dataframe row values and add data to that row
                df_investments['Current Share Price (Original Currency)'] = df_investments['Symbol'].apply(
                    lambda x: st.session_state['dfs_securities'][x]['Close'].iloc[-1]
                )

                df_investments[f'Current Share Price ({base_currency})'] = df_investments.apply(
                    lambda row: curr_conv.convert(
                        amount=row['Current Share Price (Original Currency)'],
                        currency=row['Original Currency'],
                        new_currency=base_currency,
                        date=today
                    ),
                    axis=1
                )

                df_investments[f'Current Investment Value ({base_currency})'] = df_investments['Shares Bought'] * df_investments[f'Current Share Price ({base_currency})']
                df_investments[f'Unrealised Gain/Loss ({base_currency})'] = df_investments[f'Current Investment Value ({base_currency})'] - investment_amount
                df_investments['Percentage Return'] = (df_investments[f'Unrealised Gain/Loss ({base_currency})'] / investment_amount) * 100

                st.header('Development')

                # Put together historical data for each symbol
                df_development_list = []

                for symbol, data in st.session_state['dfs_securities'].items():
                    data['Symbol'] = symbol
                    data = data[['Symbol', 'Close', 'Dividends']]
                    df_development_list.append(data)

                # Combine all dataframes into a single dataframe
                df_development = pd.concat(df_development_list)
                df_development = df_development.sort_values(['Date', 'Symbol']).reset_index()
                df_development['Date'] = df_development['Date'].dt.date
                st.write(f'Days since first investment: {len(df_development['Date'].unique())}')

                # For each day, track the user's investments' development
                cols_to_date = [
                    'Shares to Date',
                    f'Invested Capital to Date ({base_currency})',
                    f'Investment Value to Date ({base_currency})',
                    f'Unrealised Gain/Loss to Date ({base_currency})',
                    'Percentage Return'
                ]

                df_development[cols_to_date] = df_development.apply(
                    lambda x: helper.get_values_to_date(x, df_investments, base_currency),
                    axis=1,
                    result_type='expand'
                )

                st.dataframe(df_development, use_container_width=True)

                st.subheader('Dividends')

                dividends = df_development.loc[df_development['Dividends'] != 0]
                dividends = dividends.reset_index(drop=True)
                dividends = dividends.rename(
                    columns={'Dividends': 'Dividend per Share (Original Currency)'}
                )

                dividends[['Original Currency', f'Dividend per Share ({base_currency})']] = dividends.apply(
                    lambda x: helper.convert_dividends(x, base_currency, df_investments),
                    axis=1,
                    result_type='expand'
                )

                dividends[f'Dividend Income ({base_currency})'] = dividends[f'Dividend per Share ({base_currency})'] * dividends['Shares to Date']
                dividends = dividends[
                    [
                        'Date',
                        'Symbol',
                        'Shares to Date',
                        'Dividend per Share (Original Currency)',
                        f'Dividend per Share ({base_currency})',
                        f'Dividend Income ({base_currency})'
                    ]
                ]

                st.dataframe(dividends, use_container_width=True)
