"""Helper functions for investing simulator Streamlit app"""

import datetime
from dateutil.relativedelta import relativedelta
from currency_converter import CurrencyConverter

today = datetime.datetime.now()

curr_conv = CurrencyConverter(
    fallback_on_missing_rate=True,
    fallback_on_wrong_date=True
)

def is_investment_day_valid(investment_day, date_start, date_end):
    """
    Given a numerical day of the month, find out if there is any
    day with such number between the start and end date

    :param investment_day: Day in which periodic investment occurs
    :type investment_day: int
    :param date_start: Start date for investment strategy
    :type date_start: datetime.date
    :param date_end: End date for investment strategy
    :type date_end: datetime.date
    :return: Whether there is an investment day within date range
    :rtype: bool
    :return: Actual start date if date is valid
    :rtype: datetime.date
    """

    # Default start date is investment day in same month as start date
    potential_start_date = datetime.date(
        day=investment_day,
        month=date_start.month,
        year=date_start.year
    )

    # Date is correct if it lies between start and end date
    is_date_correct = date_start <= potential_start_date <= date_end

    # Increase date by a month until
    while not is_date_correct and potential_start_date <= date_end:
        potential_start_date += relativedelta(months=1)
        is_date_correct = date_start <= potential_start_date <= date_end

    return is_date_correct, potential_start_date

def get_values_to_date(row, df_investments, base_currency):
    """
    Tracks the user's investments' development on a daily basis

    :param df_investments: DataFrame of the user's investments
    :type df_investments: pd.DataFrame
    :param row: Row of DataFrame
    :type row:
    :param base_currency: Currency of user's investments
    :type base_currency: str
    :return: Number of shares owned up to a date, invested capital to date,
             investment value to date, investment gain to date and
             profit in percentage
    :rtype:
    """

    # For each row of the development DataFrame, find the user's
    # previous investments on each symbol
    is_prior_date = df_investments['Purchase Date'] <= row['Date']
    is_same_symbol = df_investments['Symbol'] == row['Symbol']
    past_data = df_investments.loc[is_prior_date & is_same_symbol]

    # Sum up the shares and capital invested up until the row's date
    num_shares_to_date = past_data['Shares Bought'].sum()
    invested_capital_to_date = round(past_data[f'Invested Capital ({base_currency})'].sum(), 2)

    close_price_converted = curr_conv.convert(
        amount=row['Close'],
        currency=past_data['Original Currency'].iloc[0],
        new_currency=base_currency,
        date=row['Date']
    )

    investment_value_to_date = round(num_shares_to_date * close_price_converted, 2)
    unrealised_gain_or_loss = investment_value_to_date - invested_capital_to_date
    profit_to_date = round((unrealised_gain_or_loss / invested_capital_to_date) * 100, 2)
    return num_shares_to_date, invested_capital_to_date, investment_value_to_date, unrealised_gain_or_loss, profit_to_date

def calculate_development_metric(metric, df_development, base_currency):
    """
    Calculate number for 1D, 1W, 1M, 6M, YTD, 1Y, 5Y, MAX metrics

    :param metric: One of 1D, 1W, 1M, 6M, YTD, 1Y, 5Y, MAX
    :type metric: str
    :param df_development: DataFrame with daily security development
    :type df_development: pandas.DataFrame
    :param base_currency: Currency in which to invest
    :type base_currency: str
    :return: Unrealised gain or loss
    :rtype: int
    :return: Percentual change
    :rtype: int
    """

    min_date = df_development['Date'].min()

    last_dates = {
        '1D': (today - relativedelta(days=1)).date(),
        '1W': (today - relativedelta(weeks=1)).date(),
        '1M': (today - relativedelta(months=1)).date(),
        '6M': (today - relativedelta(months=6)).date(),
        'YTD': max(datetime.date(day=1, month=1, year=today.year), min_date),
        '1Y': (today - relativedelta(years=1)).date(),
        '5Y': (today - relativedelta(years=5)).date(),
        'MAX': min_date
    }

    last_date = last_dates[metric]
    df_before_date = df_development.loc[df_development['Date'] <= last_date]
    if len(df_before_date) == 0:
        return '-', '-'

    last_date_gain = df_before_date[f'Unrealised Gain/Loss to Date ({base_currency})'].iloc[-1]
    newest_gain = df_development[f'Unrealised Gain/Loss to Date ({base_currency})'].iloc[-1]

    last_date_profit = df_before_date['Percentage Return'].iloc[-1]
    newest_profit = df_development['Percentage Return'].iloc[-1]

    gain_or_loss_change = newest_gain - last_date_gain
    pct_change = newest_profit - last_date_profit
    gain_or_loss_change = f'{'+' if gain_or_loss_change >= 0 else ''}{gain_or_loss_change:.2f}'

    return gain_or_loss_change, f'{pct_change:.2f}%'

def convert_dividends(row, base_currency, df_investments):
    """
    Convert dividends to user's currency.

    :return: Converted dividends
    :rtype: float
    """

    is_same_symbol = row['Symbol'] == df_investments['Symbol']
    original_currency = df_investments.loc[is_same_symbol, 'Original Currency'].iloc[0]
    dividend_converted = round(
        curr_conv.convert(
            amount=row['Dividend per Share (Original Currency)'],
            currency=original_currency,
            new_currency=base_currency,
            date=row['Date']
        ),
        2
    )

    return original_currency, dividend_converted
