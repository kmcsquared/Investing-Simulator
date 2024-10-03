"""Streamlit app to simulate investments over a period of time in the past"""

import datetime
import pandas as pd
import streamlit as st
import yfinance as yf
import plotly.express as px
import helper

st.set_page_config(layout='wide')
st.title('Investing Simulator (Dollar-Cost Averaging)')
st.write(
    '''
    - This app allows you to simulate how your investments would have performed over time 
    if you had invested on a monthly basis, inspired by the [dollar-cost averaging](
    https://www.investopedia.com/terms/d/dollarcostaveraging.asp) strategy.

    - The simulation assumes that it is possible to buy fractional shares
    and that there are no currency exchange fees.

    - If the scheduled investment happens to be on a day when the market 
    is closed, the buy order will be executed in the next market opening.
    
    - Orders are executed at market open by default and are compared against
    market close prices for each date.
    '''
)

today = datetime.datetime.now()

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
        investment_frequency = st.selectbox(
            label='How often will you invest?',
            options=['Daily', 'Weekly', 'Monthly'],
            index=2,
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
            options=sorted(helper.curr_conv.currencies),
            index=sorted(helper.curr_conv.currencies).index('USD'),
            help='''
            If the security is traded in a currency that is not your base currency, 
            a currency exchange will occur.
            '''
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

    # If user has not entered any ticker symbols
    if input_ticker_symbol == '':
        st.write('Please enter at least one ticker symbol.')

    # If user has entered a symbol
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

            INVESTMENT_EXISTS = False   # Flag to output message if no investment exists

            # Use session_state to store yfinance data and
            # avoid downloading from yfinance after slider update
            if 'dfs_downloads' not in st.session_state:
                st.session_state['dfs_downloads'] = {}  # DataFrames of symbols with retrieved data

            # Get the buy price for each investment date and symbol
            current_investment_date = datetime.date(
                day=date_start.day,
                month=date_start.month,
                year=date_start.year
            )

            while current_investment_date <= date_end:
                for symbol in sorted(symbols):
                    # Create unique key for search parameters to store
                    # yfinance data in session_state
                    key = f'{symbol}//{date_start}//{date_end}//{investment_frequency}//{investment_amount}'
                    if key not in st.session_state['dfs_downloads']:
                        df_security = yf.download(
                            tickers=symbol,
                            start=date_start,
                            end=date_end,
                            actions=True,
                            rounding=True
                        )

                        # If no data was found for symbol
                        if len(df_security) == 0:
                            st.write(
                                f'''
                                Unfortunately no price data was found for {symbol} from
                                {date_start:%B %d %Y} until {date_end:%B %d %Y}.
                                '''
                            )

                            continue

                        # Store yfinance data under unique key in session_state
                        st.session_state['dfs_downloads'][key] = df_security

                    # Shorter variable name to avoid typing session_state...
                    dfs_downloads = st.session_state['dfs_downloads'].copy()
                    # Create row for DataFrame
                    row = []

                    # If market is open, buy on investment date
                    market_open_dates = dfs_downloads[key].index.date
                    is_market_open = current_investment_date in market_open_dates
                    if is_market_open:
                        buy_price_original = dfs_downloads[key].loc[
                            market_open_dates == current_investment_date,
                            'Open'
                        ].iloc[0]

                        actual_investment_date = current_investment_date
                        INVESTMENT_EXISTS = True

                    # If market is closed, buy at next market open
                    else:
                        is_future_date = market_open_dates > current_investment_date
                        # If market has not opened yet in the future, break
                        if is_future_date.sum() == 0:
                            st.write(
                                f'''
                                No market data was found for {symbol} scheduled investment
                                on {current_investment_date} or the following market open.
                                '''
                            )
                            break

                        # If market has opened in the future, buy in first opportunity
                        future_dates = dfs_downloads[key].loc[is_future_date]
                        next_market_open = future_dates.reset_index().iloc[0]
                        buy_price_original = next_market_open['Open']
                        actual_investment_date = next_market_open['Date'].date()
                        INVESTMENT_EXISTS = True

                    # Convert buy price from security's currency to base currency
                    currency_security = tickers[symbol].info['currency']
                    if currency_security == base_currency:
                        buy_price_converted = buy_price_original
                    else:
                        buy_price_converted = helper.curr_conv.convert(
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
                    row.append(round(buy_price_original, 2))
                    row.append(round(buy_price_converted, 2))
                    row.append(round(investment_amount, 2))
                    rows.append(row)

                # Once the investment date is covered for
                # all symbols, move on to next date
                current_investment_date = helper.update_investment_date(
                    current_investment_date,
                    investment_frequency
                )

            # If unable to execute any buy orders
            if not INVESTMENT_EXISTS:
                st.write(
                    '''
                    There was no data retrieved for any investments between the selected
                    start and end dates. Perhaps try a different investment day.
                    '''
                )

            # If able to execute at least 1 buy order
            else:
                first_investment_date = rows[0][0]
                last_investment_date = rows[-1][0]

                st.write(
                    f'''
                    You will invest in the following {NUM_SECURITIES_INVESTED}
                    [{'security' if NUM_SECURITIES_INVESTED == 1 else 'securities'}](
                    https://www.investopedia.com/terms/s/security.asp) on a
                    {investment_frequency.lower()} basis from the first available
                    investment date ({first_investment_date:%B %d, %Y}) until the last
                    available investment date ({last_investment_date:%B %d, %Y}).
                    '''
                )

                # Write out the different securities to invest in
                NUM_COLS = 4
                cols_securities = st.columns(NUM_COLS)
                for i, security in enumerate(sorted(securities_invested)):
                    with cols_securities[i%NUM_COLS]:
                        st.write(f'{i+1}. {security}')

                # Create monthly investments DataFrame from rows
                DF_INVESTMENTS = pd.DataFrame(
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

                # When investing daily and meeting a closed market date,
                # the simulation would invest twice in the next open date
                if investment_frequency == 'Daily':
                    DF_INVESTMENTS = DF_INVESTMENTS.drop_duplicates(['Purchase Date', 'Symbol'])

                # Convert to datetime.date
                DF_INVESTMENTS['Purchase Date'] = pd.to_datetime(DF_INVESTMENTS['Purchase Date'])
                DF_INVESTMENTS['Purchase Date'] = DF_INVESTMENTS['Purchase Date'].dt.date

                st.header('Transactions')
                st.write('Your periodic investments are shown below.')
                st.dataframe(DF_INVESTMENTS, use_container_width=True)

                # Find current investment value
                # Generate key for correct yfinance data retrieval
                DF_INVESTMENTS['Key'] = DF_INVESTMENTS['Symbol'] + f'//{date_start}//{date_end}//{investment_frequency}//{investment_amount}'
                # Match values from dictionary to DataFrame row values and add data to that row
                DF_INVESTMENTS['Current Share Price (Original Currency)'] = DF_INVESTMENTS['Key'].apply(
                    lambda x: round(dfs_downloads[x]['Close'].iloc[-1], 2)
                )

                # Convert share price
                DF_INVESTMENTS[f'Current Share Price ({base_currency})'] = DF_INVESTMENTS.apply(
                    lambda row: round(
                        helper.curr_conv.convert(
                            amount=row['Current Share Price (Original Currency)'],
                            currency=row['Original Currency'],
                            new_currency=base_currency,
                            date=date_end
                        ),
                        2
                    ),
                    axis=1
                )

                # Calculate for each day within date range
                DF_INVESTMENTS[f'Current Investment Value ({base_currency})'] = DF_INVESTMENTS['Shares Bought'] * DF_INVESTMENTS[f'Current Share Price ({base_currency})']
                DF_INVESTMENTS[f'Unrealised Gain/Loss ({base_currency})'] = DF_INVESTMENTS[f'Current Investment Value ({base_currency})'] - investment_amount
                DF_INVESTMENTS['Percentage Return'] = (DF_INVESTMENTS[f'Unrealised Gain/Loss ({base_currency})'] / investment_amount) * 100

                st.header('Development')

                st.write(
                    '''
                    - The metrics below show the overall gain (or loss) of the scheduled
                    investements over a time period, as well as the difference in 
                    percentage return of the investment value since then.

                    - You can click on the legend to show/hide each symbol.
                    '''
                )

                # Put together historical data for each symbol
                df_development_list = []

                for key, data in dfs_downloads.items():
                    symbol = key.split('//')[0]
                    data['Symbol'] = symbol
                    data = data[['Symbol', 'Close', 'Dividends']]
                    df_development_list.append(data)

                # Combine all DataFrames into a single DataFrame
                df_development = pd.concat(df_development_list)
                df_development = df_development.sort_values(['Date', 'Symbol']).reset_index()
                df_development['Date'] = df_development['Date'].dt.date

                # For each day, track the user's investments' development
                cols_to_date = [
                    'Shares to Date',
                    f'Invested Capital to Date ({base_currency})',
                    f'Investment Value to Date ({base_currency})',
                    f'Unrealised Gain/Loss to Date ({base_currency})',
                    'Percentage Return'
                ]

                df_development[cols_to_date] = df_development.apply(
                    lambda row: helper.get_values_to_date(row, DF_INVESTMENTS, base_currency),
                    axis=1,
                    result_type='expand'
                )

                # Keep only dates where all symbols have data
                counts = df_development['Date'].value_counts()
                dates_with_all_symbols = counts.index[counts.eq(NUM_SECURITIES_INVESTED)]
                dates_with_all_symbols = df_development['Date'].isin(dates_with_all_symbols)
                df_all_symbols_per_date = df_development.loc[dates_with_all_symbols].copy()
                # Aggregate symbols by date
                cols_agg = ['Invested Capital', 'Investment Value', 'Unrealised Gain/Loss']
                cols_agg = [f'{col} to Date ({base_currency})' for col in cols_agg]
                df_grouped = df_all_symbols_per_date.groupby('Date')[cols_agg].sum()
                df_grouped = df_grouped.reset_index()
                df_grouped['Percentage Return'] = (df_grouped[f'Unrealised Gain/Loss to Date ({base_currency})'] / df_grouped[f'Invested Capital to Date ({base_currency})']) * 100
                df_grouped['Percentage Return'] = df_grouped['Percentage Return'].round(2)
                df_grouped['Symbol'] = '--OVERALL--'

                # Display period performance metrics
                metrics = ['1D', '1W', '1M', '6M', 'YTD', '1Y', '5Y', 'MAX']
                metric_cols = st.columns(len(metrics))  # Show metrics horizontally
                for col_idx, metric in enumerate(metrics):
                    # Calculate metric
                    metric_gain_loss, metric_pct_change = helper.calculate_development_metric(
                        metric,
                        df_grouped.loc[df_grouped['Symbol'] == '--OVERALL--'],
                        base_currency
                    )

                    # Show metric
                    with metric_cols[col_idx]:
                        st.metric(
                            label=f'{metric} ({base_currency})',
                            value=metric_gain_loss,
                            delta=metric_pct_change,
                            delta_color='off' if metric_pct_change == '-' else 'normal'
                        )

                df_development_plot = pd.concat([df_development, df_grouped], ignore_index=True)
                df_development_plot = df_development_plot.sort_values(['Date', 'Symbol'])
                df_development_plot = df_development_plot.reset_index(drop=True)
                # Round numbers to 2 decimal figures
                df_development_plot[f'Unrealised Gain/Loss to Date ({base_currency})'] = df_development_plot[f'Unrealised Gain/Loss to Date ({base_currency})'].round(2)
                df_development_plot[f'Investment Value to Date ({base_currency})'] = df_development_plot[f'Investment Value to Date ({base_currency})'].round(2)
                # st.dataframe(df_development_plot, use_container_width=True)

                # Plot gain/loss and percentage return in separate tabs
                tab_gain_loss, tab_pct_return = st.tabs(
                    ['Unrealised Gain/Loss', 'Percentage Return']
                )

                with tab_gain_loss:
                    fig_gain_loss = px.line(
                        df_development_plot,
                        x='Date',
                        y=f'Unrealised Gain/Loss to Date ({base_currency})',
                        color='Symbol',
                    )

                    fig_gain_loss.update_traces(hovertemplate=None)
                    fig_gain_loss.update_layout(
                        yaxis_title=f'Unrealised Gain/Loss ({base_currency})',
                        hovermode='x unified'
                    )

                    st.plotly_chart(fig_gain_loss)

                with tab_pct_return:

                    fig_pct_return = px.line(
                        df_development_plot,
                        x='Date',
                        y='Percentage Return',
                        color='Symbol',
                    )

                    fig_pct_return.update_traces(hovertemplate=None)
                    fig_pct_return.update_layout(
                        hovermode='x unified'
                    )

                    # Select only overall performance by default
                    # https://stackoverflow.com/questions/74322004/how-to-have-one-item-in-the-legend-selected-by-default-in-plotly-dash
                    fig_pct_return.update_traces(visible='legendonly')
                    fig_pct_return.data[0].visible = True
                    st.plotly_chart(fig_pct_return)

                st.header('Portfolio Distribution')

                # Slider to update pie chart over time
                date_slider = st.slider(
                    label='Analyse portofolio distribution by date',
                    min_value=df_all_symbols_per_date['Date'].min(),
                    max_value=df_all_symbols_per_date['Date'].max(),
                    format='MMM D, YYYY'
                )

                # Get values up until slider date
                df_pie = df_all_symbols_per_date.copy()
                df_pie = df_pie.loc[df_pie['Date'] <= date_slider]

                # Plot invested capital and actual value in separate columns
                colums_pie_streamlit = st.columns(2)
                cols_pie = [
                    f'Invested Capital to Date ({base_currency})',
                    f'Investment Value to Date ({base_currency})',
                ]

                # Get last values for each security, add them together
                # and plot the pie chart
                for idx, col_df in enumerate(cols_pie):
                    total_amount = df_pie[col_df].iloc[-NUM_SECURITIES_INVESTED:].sum()
                    # Capital as int, value as float
                    total_amount = round(total_amount) if idx == 0 else round(total_amount, 2)

                    if col_df == f'Investment Value to Date ({base_currency})':
                        DELTA = df_pie['Percentage Return'].iloc[-NUM_SECURITIES_INVESTED:].mean()
                        DELTA = f'{DELTA:.2f}%'
                    else:
                        DELTA = None

                    with colums_pie_streamlit[idx]:
                        st.metric(label=col_df, value=total_amount, delta=DELTA)
                        fig_pie = px.pie(
                            df_pie.iloc[-NUM_SECURITIES_INVESTED:],
                            values=col_df,
                            names='Symbol'
                        )
                        st.plotly_chart(fig_pie)

                st.header('Dividends')

                # Get dividends
                is_dividend = df_development['Dividends'] != 0
                if is_dividend.sum() == 0:
                    st.write(
                        f'''
                        There are no dividends for any of your investments
                        during the period {date_start:%B %d %Y} until {date_end:%B %d %Y}.
                        '''
                    )
                else:

                    dividends = df_development.loc[is_dividend]

                    dividends = dividends.reset_index(drop=True)
                    dividends = dividends.rename(
                        columns={'Dividends': 'Dividend per Share (Original Currency)'}
                    )

                    # Convert dividends to base currency
                    dividends[['Original Currency', f'Dividend per Share ({base_currency})']] = dividends.apply(
                        lambda x: helper.convert_dividends(x, base_currency, DF_INVESTMENTS),
                        axis=1,
                        result_type='expand'
                    )

                    # Calculate income from dividends
                    dividends[f'Dividend Income ({base_currency})'] = dividends[f'Dividend per Share ({base_currency})'] * dividends['Shares to Date']
                    dividends[f'Dividend Income ({base_currency})'] = dividends[f'Dividend Income ({base_currency})'].round(2)
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

                    st.dataframe(dividends)
