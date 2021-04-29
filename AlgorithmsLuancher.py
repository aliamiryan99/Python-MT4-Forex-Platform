# %% -----------|| Main Section ||----------
from datetime import datetime
import copy
from Simulation import Utility as ut

from tqdm import tqdm

from Simulation.LuncherConfig import LauncherConfig

from Simulation import Simulation
from Simulation.Config import Config
from Simulation import Outputs

data = {}


def launch():
    # Data
    symbols = LauncherConfig.symbols
    start_indexes, end_indexes, configs, algorithm_data_total, algorithm_start_indexes, \
    algorithm_end_indexes, trailing_data_total, trailing_start_indexes, trailing_end_indexes = initialize_data()

    # Algorithms
    algorithm_data, trailing_data, history_size, algorithms, re_entrance_algorithms, recovery_algorithms, close_modes, \
    tp_sl_tools, trailing_tools, account_managements, market, last_ticket, last_algorithm_signal_ticket, \
    algorithm_histories, trailing_histories, buy_open_positions_lens, sell_open_positions_lens, last_buy_closed, \
    last_sell_closed, trade_buy_in_candle_counts, trade_sell_in_candle_counts, virtual_buys, virtual_sells,\
    recovery_trades = initialize_algorithms(symbols, start_indexes, configs, algorithm_data_total,
                                            algorithm_start_indexes, trailing_data_total, trailing_start_indexes)

    # Back Test
    back_test_length = end_indexes[symbols[0]] - start_indexes[symbols[0]]
    for ii in tqdm(range(back_test_length)):
        i = start_indexes[symbols[0]] + ii
        data_time = data[symbols[0]][i]['Time']
        # Market Update Section
        market.update(data_time)

        for symbol in symbols:
            i = start_indexes[symbol] + ii
            data_time = data[symbol][i]['Time']

            # Select Symbol Configuration
            history = data[symbol][i - history_size:i + 1]
            config = configs[symbol]
            algorithm = algorithms[symbol]
            tp_sl_tool = tp_sl_tools[symbol]
            trailing_tool = trailing_tools[symbol]
            re_entrance_algorithm = re_entrance_algorithms[symbol]
            recovery_algorithm = recovery_algorithms[symbol]
            recovery_trades_symbol = recovery_trades[symbol]

            # Debug Section
            # if data_time == datetime(year=2017, month=4, day=23, hour=0, minute=0):
            #     print(data_time)

            # Ignore Holidays
            if history[-1]['Volume'] == 0:
                continue

            # Update History
            signal, price = update_history(history, algorithm_histories, trailing_histories, algorithm,
                                           re_entrance_algorithm, trailing_tool, tp_sl_tool, recovery_algorithm,
                                           trade_buy_in_candle_counts, trade_sell_in_candle_counts, config, symbol,
                                           market.equity)

            # Take Profit And Stop Loss
            take_profit, stop_loss, first_stop_loss, take_profit_buy, stop_loss_buy, take_profit_sell,\
            stop_loss_sell = 0, 0, 0, 0, 0, 0, 0
            if signal == 1 or signal == -1:
                take_profit, stop_loss, first_stop_loss, take_profit_buy, stop_loss_buy, take_profit_sell,\
                stop_loss_sell = tp_sl(close_modes, tp_sl_tool, algorithm_histories, signal, price, symbol)

            # Account Management
            volume = account_managements[symbol].calculate(market.balance, abs(first_stop_loss - price), symbol)

            # Algorithm Execution
            last_ticket = algorithm_execute(market, history, signal, price, config, data_time, symbol, take_profit_buy,
                                            stop_loss_buy, take_profit_sell, stop_loss_sell, volume, last_ticket,
                                            last_algorithm_signal_ticket, virtual_buys, virtual_sells,
                                            trade_buy_in_candle_counts, trade_sell_in_candle_counts, recovery_trades_symbol)

            # Trailing Stop Section
            trailing(market, history, trailing_histories, data_time, trailing_tool, config, close_modes,
                     last_buy_closed, last_sell_closed, virtual_buys, virtual_sells, symbol)

            if last_buy_closed[symbol] is None:
                last_buy_closed[symbol] = market.get_last_buy_closed(symbol)
            if last_sell_closed[symbol] is None:
                last_sell_closed[symbol] = market.get_last_sell_closed(symbol)

            # Virtual Tp Sl Check
            virtuals_check(virtual_buys[symbol], virtual_sells[symbol], history, last_buy_closed, last_sell_closed,
                           symbol, Config.spreads[symbol])

            # Re Entrance Algorithm Section
            last_ticket = re_entrance(market, config, tp_sl_tool, close_modes, re_entrance_algorithm, history,
                                      algorithm_histories, data_time,
                                      buy_open_positions_lens, sell_open_positions_lens, last_buy_closed,
                                      last_sell_closed, last_algorithm_signal_ticket, price, take_profit_buy,
                                      stop_loss_buy, take_profit_sell, stop_loss_sell, trade_buy_in_candle_counts,
                                      trade_sell_in_candle_counts, virtual_buys, virtual_sells, volume, last_ticket,
                                      symbol)

            if config.recovery_enable:
                for i in range(len(recovery_trades_symbol)):
                    recovery_signal, modify_signals = recovery_algorithm.on_tick(recovery_trades_symbol[i])
                    if recovery_signal['Signal'] == 1:
                        recovery_signal['TP'] += history[-1]['Close']
                        trade = market.buy(data_time, recovery_signal['Price'], symbol, recovery_signal['TP'], 0, recovery_signal['Volume'], last_ticket)
                        if trade is not None:
                            last_ticket += 1
                            recovery_trades_symbol[i].append(trade)
                        for modify_signal in modify_signals:
                            modify_signal['TP'] += history[-1]['Close']
                            market.modify(modify_signal['Ticket'], modify_signal['TP'], 0)
                    elif recovery_signal['Signal'] == -1:
                        recovery_signal['TP'] += history[-1]['Close']
                        trade = market.sell(data_time, recovery_signal['Price'], symbol, recovery_signal['TP'], 0,
                                           recovery_signal['Volume'], last_ticket)
                        if trade is not None:
                            last_ticket += 1
                            recovery_trades_symbol[i].append(trade)
                        for modify_signal in modify_signals:
                            modify_signal['TP'] += history[-1]['Close']
                            market.modify(modify_signal['Ticket'], modify_signal['TP'], 0)
                recovery_trades_copy = copy.copy(recovery_trades_symbol)
                for i in range(len(recovery_trades_copy)):
                    if (recovery_trades_copy[i][0]['Type'] == 'Buy' and history[-1]['High'] > recovery_trades_copy[i][0]['TP']) or \
                            (recovery_trades_copy[i][0]['Type'] == 'Sell' and history[-1]['Low'] + Config.spreads[symbol] < recovery_trades_copy[i][0]['TP']):
                        recovery_algorithm.tp_touched(recovery_trades_copy[i][0]['Ticket'])
                        recovery_trades_symbol.remove(recovery_trades_copy[i])


    # Exit Section
    market.exit()
    return market


def initialize_data():
    # Simulation init
    global data
    symbols = LauncherConfig.symbols
    symbols_ratio = LauncherConfig.symbols_ratio
    algorithm_time_frame = LauncherConfig.algorithm_time_frame
    trailing_time_frame = LauncherConfig.trailing_time_frame
    Config.time_frame_show = algorithm_time_frame
    Config.symbols_list.clear()
    Config.symbols_dict.clear()
    for i in range(len(symbols)):
        symbol = symbols[i]
        Config.symbols_list.append(symbol)
        Config.symbols_dict[symbol] = i
        Config.symbols_show[symbol] = 1
    Simulation.initialize()
    start_time = datetime.strptime(Config.start_date, Config.date_format)
    end_time = datetime.strptime(Config.end_date, Config.date_format)
    # algorithm init
    data_total = Simulation.data
    start_indexes = {}
    end_indexes = {}

    for i in range(len(symbols)):
        symbol = symbols[i]
        start_indexes[symbol] = Outputs.index_date_v2(data_total[Config.symbols_dict[symbol]], start_time)
        end_indexes[symbol] = Outputs.index_date_v2(data_total[Config.symbols_dict[symbol]], end_time)

    data_algorithm_paths = []
    data_trailing_paths = []
    for i in range(len(symbols)):
        symbol = symbols[i]
        data_algorithm_paths += ["Data/" + Config.categories_list[symbol] + "/" + symbol + "/" + algorithm_time_frame + ".csv"]
        data_trailing_paths += ["Data/" + Config.categories_list[symbol] + "/" + symbol + "/" + trailing_time_frame + ".csv"]
    algorithm_data = ut.csv_to_df(data_algorithm_paths, date_format=Config.date_format)
    trailing_data = ut.csv_to_df(data_trailing_paths, date_format=Config.date_format)

    algorithm_start_indexes = {}
    trailing_start_indexes = {}
    algorithm_end_indexes = {}
    trailing_end_indexes = {}
    configs = {}
    for i in range(len(symbols)):
        symbol = symbols[i]
        algorithm_data[i] = algorithm_data[i][algorithm_data[i].Volume != 0]
        trailing_data[i] = trailing_data[i][trailing_data[i].Volume != 0]
        algorithm_start_indexes[symbol] = Outputs.index_date(algorithm_data[i], start_time)
        trailing_start_indexes[symbol] = Outputs.index_date(algorithm_data[i], start_time)
        algorithm_end_indexes[symbol] = Outputs.index_date(algorithm_data[i], end_time)
        trailing_end_indexes[symbol] = Outputs.index_date(algorithm_data[i], end_time)
        configs[symbol] = LauncherConfig(symbol, algorithm_data[i].to_dict('Records'), algorithm_start_indexes[symbol],
                                         symbols_ratio[i])
    for symbol in symbols:
        data[symbol] = data_total[Config.symbols_dict[symbol]]

    return start_indexes, end_indexes, configs, algorithm_data, algorithm_start_indexes, algorithm_end_indexes, \
           trailing_data, trailing_start_indexes, trailing_end_indexes


def initialize_algorithms(symbols, start_indexes, configs, algorithm_data_total,
                          algorithm_start_indexes, trailing_data_total,
                          trailing_start_indexes):
    global data
    algorithm_data = {}
    trailing_data = {}

    for i in range(len(symbols)):
        algorithm_data[symbols[i]] = algorithm_data_total[i].to_dict('Records')
        trailing_data[symbols[i]] = trailing_data_total[i].to_dict('Records')
    # history
    history_size = LauncherConfig.history_size

    # Algorithm
    algorithms = {}
    for symbol in symbols:
        algorithms[symbol] = configs[symbol].algorithm

    # Re entrance
    re_entrance_algorithms = {}
    for symbol in symbols:
        re_entrance_algorithms[symbol] = configs[symbol].repairment_algorithm

    # Recovery
    recovery_algorithms = {}
    for symbol in symbols:
        recovery_algorithms[symbol] = configs[symbol].recovery_algorithm

    # Algorithm Tools
    close_modes = {}
    tp_sl_tools = {}
    trailing_tools = {}
    for symbol in symbols:
        close_modes[symbol] = configs[symbol].close_mode
        tp_sl_tools[symbol] = configs[symbol].tp_sl_tool
        trailing_tools[symbol] = configs[symbol].trailing_tool

    # Account Management
    account_managements = {}
    for symbol in symbols:
        account_managements[symbol] = configs[symbol].account_management

    # Market Config
    start_time = datetime.strptime(Config.start_date, Config.date_format)
    end_time = datetime.strptime(Config.end_date, Config.date_format)
    market = Simulation.Simulation(Config.leverage, Config.balance, start_time, end_time)

    # Launcher Requirement
    last_ticket = 0
    last_algorithm_signal_ticket = {}
    algorithm_histories = {}
    trailing_histories = {}
    buy_open_positions_lens = {}
    sell_open_positions_lens = {}
    last_buy_closed = {}
    last_sell_closed = {}
    trade_buy_in_candle_counts = {}
    trade_sell_in_candle_counts = {}
    virtual_buys = {}
    virtual_sells = {}
    recovery_trades = {}
    for symbol in symbols:
        row = data[symbol][start_indexes[symbol]]

        algorithm_histories[symbol] = algorithm_data[symbol][
                                      algorithm_start_indexes[symbol] - history_size:algorithm_start_indexes[symbol]]
        trailing_histories[symbol] = trailing_data[symbol][
                                     trailing_start_indexes[symbol] - history_size:trailing_start_indexes[symbol]]

        buy_open_positions_lens[symbol] = 0
        sell_open_positions_lens[symbol] = 0

        trade_buy_in_candle_counts[symbol] = 0
        trade_sell_in_candle_counts[symbol] = 0

        virtual_buys[symbol] = []
        virtual_sells[symbol] = []

        recovery_trades[symbol] = []

    return algorithm_data, trailing_data, history_size, algorithms, re_entrance_algorithms, recovery_algorithms, close_modes, \
           tp_sl_tools, trailing_tools, account_managements, market, last_ticket, last_algorithm_signal_ticket, \
           algorithm_histories, trailing_histories, buy_open_positions_lens, sell_open_positions_lens, last_buy_closed, \
           last_sell_closed, trade_buy_in_candle_counts, trade_sell_in_candle_counts, virtual_buys, virtual_sells,\
           recovery_trades


def get_time_id(time, time_frame):
    identifier = time.day
    if time_frame == "W1":
        identifier = time.isocalendar()[1]
    if time_frame == "H12":
        identifier = time.day * 2 + time.hour // 12
    if time_frame == "H4":
        identifier = time.day * 6 + time.hour // 4
    if time_frame == "H1":
        identifier = time.day * 24 + time.hour
    if time_frame == "M30":
        identifier = time.hour * 2 + time.minute // 30
    if time_frame == "M15":
        identifier = time.hour * 4 + time.minute // 15
    if time_frame == "M5":
        identifier = time.hour * 12 + time.minute // 5
    if time_frame == "M1":
        identifier = time.hour * 60 + time.minute
    return identifier


def update_history(history, algorithm_histories, trailing_histories, algorithm, re_entrance_algorithm, trailing_tool, tp_sl_tool,
                   recovery_algorithm, trade_buy_in_candle_counts, trade_sell_in_candle_counts, config, symbol, equity):
    # Algorithm Time ID
    history_time = get_time_id(history[-1]['Time'], config.algorithm_time_frame)
    algorithm_time = get_time_id(algorithm_histories[symbol][-1]['Time'], config.algorithm_time_frame)
    if history_time != algorithm_time:
        # New Candle Open Section
        last_candle = {"Time": history[-1]['Time'], "Open": history[-1]['Open'], "High": history[-1]['High'],
                       "Low": history[-1]['Low'], "Close": history[-1]['Close'],"Volume": history[-1]['Volume']}
        algorithm_histories[symbol].append(last_candle)
        algorithm_histories[symbol].pop(0)
        signal, price = algorithm.on_data(algorithm_histories[symbol][-1], equity)
        recovery_algorithm.on_data(algorithm_histories[symbol][-1])
        tp_sl_tool.on_data(algorithm_histories[symbol][-1])
    else:
        # Update Last Candle Section
        algorithm_histories[symbol][-1]['High'] = max(algorithm_histories[symbol][-1]['High'],history[-1]['High'])
        algorithm_histories[symbol][-1]['Low'] = min(algorithm_histories[symbol][-1]['Low'], history[-1]['Low'])
        algorithm_histories[symbol][-1]['Close'] = history[-1]['Close']
        algorithm_histories[symbol][-1]['Volume'] += history[-1]['Volume']
        # Signal Section
        signal, price = algorithm.on_tick()

    # Trailing Time ID
    trailing_time = get_time_id(trailing_histories[symbol][-1]['Time'], config.trailing_time_frame)
    history_time = get_time_id(history[-1]['Time'], config.trailing_time_frame)

    if history_time != trailing_time:
        last_candle = {"Time": history[-1]['Time'], "Open": history[-1]['Open'], "High": history[-1]['High'],
                       "Low": history[-1]['Low'], "Close": history[-1]['Close'],
                       "Volume": history[-1]['Volume']}
        trailing_histories[symbol].append(last_candle)
        trailing_histories[symbol].pop(0)
        trade_buy_in_candle_counts[symbol] = 0
        trade_sell_in_candle_counts[symbol] = 0
        trailing_tool.on_data(trailing_histories[symbol])
        re_entrance_algorithm.on_data()
    else:
        trailing_histories[symbol][-1]['High'] = max(trailing_histories[symbol][-1]['High'],
                                                     history[-1]['High'])
        trailing_histories[symbol][-1]['Low'] = min(trailing_histories[symbol][-1]['Low'], history[-1]['Low'])
        trailing_histories[symbol][-1]['Close'] = history[-1]['Close']
        trailing_histories[symbol][-1]['Volume'] += history[-1]['Volume']

    return signal, price


def tp_sl(close_modes, tp_sl_tool, algorithm_histories, signal, price, symbol):
    take_profit, stop_loss, first_stop_loss = 0, 0, 0
    take_profit_buy, stop_loss_buy = 0, 0
    take_profit_sell, stop_loss_sell = 0, 0
    if close_modes[symbol] == 'tp_sl' or close_modes[symbol] == 'both':
        take_profit_buy, stop_loss_buy = tp_sl_tool.on_tick(algorithm_histories[symbol], 'buy')
        take_profit_sell, stop_loss_sell = tp_sl_tool.on_tick(algorithm_histories[symbol], 'sell')
        if take_profit_buy != 0:
            take_profit_buy += price
        if stop_loss_buy != 0:
            stop_loss_buy += price
        if take_profit_sell != 0:
            take_profit_sell += price
        if stop_loss_sell != 0:
            stop_loss_sell += price
        take_profit, stop_loss = take_profit_buy, stop_loss_buy
        if signal == -1:
            take_profit, stop_loss = take_profit_sell, stop_loss_sell
        first_stop_loss = stop_loss
    return take_profit, stop_loss, first_stop_loss, take_profit_buy, stop_loss_buy, take_profit_sell, stop_loss_sell


def algorithm_execute(market, history, signal, price, config, data_time, symbol, take_profit_buy, stop_loss_buy, take_profit_sell,
                      stop_loss_sell, volume, last_ticket, last_algorithm_signal_ticket, virtual_buys, virtual_sells,
                      trade_buy_in_candle_counts, trade_sell_in_candle_counts, recovery_trades):
    if signal == 1:  # buy signal
        if config.multi_position or (
                not config.multi_position and market.get_open_buy_positions_count(symbol) == 0):
            if not config.enable_max_trade_per_candle or \
                    (config.enable_max_trade_per_candle and trade_buy_in_candle_counts[symbol] < config.max_trade_per_candle):
                if config.algorithm_force_price and history[-1]['Low'] <= price <= history[-1]['High'] or\
                        not config.algorithm_force_price:
                    if not config.algorithm_force_price and not history[-1]['Low'] <= price <= history[-1]['High']:
                        price = history[-1]['Open']
                    if not config.algorithm_virtual_signal:
                        trade = market.buy(data_time, price, symbol, take_profit_buy, stop_loss_buy, volume, last_ticket)
                        if trade is not None:
                            recovery_trades.append([trade])
                            last_algorithm_signal_ticket[symbol] = last_ticket
                            last_ticket += 1
                            trade_buy_in_candle_counts[symbol] += 1
                    else:
                        virtual_buys[symbol].append({'start_gmt': data_time,
                                                     'start_price': price,
                                                     'symbol': symbol, 'take_profit': take_profit_buy,
                                                     'stop_loss': stop_loss_buy,
                                                     'volume': volume, 'closed_volume': 0, 'ticket': -1})
                        last_algorithm_signal_ticket[symbol] = -1
                        trade_buy_in_candle_counts[symbol] += 1

    elif signal == -1:  # sell signal
        if config.multi_position or (
                not config.multi_position and market.get_open_sell_positions_count(symbol) == 0):
            if not config.enable_max_trade_per_candle or \
                    (config.enable_max_trade_per_candle and trade_sell_in_candle_counts[
                        symbol] < config.max_trade_per_candle):
                if config.algorithm_force_price and history[-1]['Low'] <= price <= history[-1]['High'] or\
                        not config.algorithm_force_price:
                    if not config.algorithm_force_price and not history[-1]['Low'] <= price <= history[-1]['High']:
                        price = history[-1]['Open']
                    if not config.algorithm_virtual_signal:
                        trade = market.sell(data_time, price, symbol, take_profit_sell, stop_loss_sell, volume, last_ticket)
                        if trade is not None:
                            recovery_trades.append([trade])
                            last_algorithm_signal_ticket[symbol] = last_ticket
                            last_ticket += 1
                            trade_sell_in_candle_counts[symbol] += 1
                    else:
                        virtual_sells[symbol].append({'start_gmt': data_time,
                                                      'start_price': price,
                                                      'symbol': symbol, 'take_profit': take_profit_sell,
                                                      'stop_loss': stop_loss_sell,
                                                      'volume': volume, 'closed_volume': 0, 'ticket': -1})
                        last_algorithm_signal_ticket[symbol] = -1
                        trade_sell_in_candle_counts[symbol] += 1
    return last_ticket


def trailing(market, history, trailing_histories, data_time, trailing_tool, config, close_modes, last_buy_closed,
             last_sell_closed, virtual_buys, virtual_sells, symbol):
    last_buy_closed[symbol] = None
    last_sell_closed[symbol] = None
    if close_modes[symbol] == 'trailing' or close_modes[symbol] == 'both':
        open_buy_positions = copy.deepcopy(market.open_buy_positions) + virtual_buys[symbol]
        for position in open_buy_positions:
            if position['Symbol'] == symbol:
                entry_point = Outputs.index_date_v2(trailing_histories[symbol],
                                                    position['start_gmt'])
                is_close, close_price = trailing_tool.on_tick(trailing_histories[symbol],
                                                              entry_point, 'buy', data_time)
                if is_close:
                    if history[-1]['Low'] <= close_price <= history[-1]['High']:
                        if position['Ticket'] == -1:
                            last_buy_closed[symbol] = virtual_close(position, history[-1]['Time'], close_price)
                            virtual_buys[symbol].remove(position)
                        else:
                            market.close(data_time, close_price, position['Volume'], position['Ticket'])
                    elif not config.force_close_on_algorithm_price and history[-1]['Open'] < close_price:
                        if position['Ticket'] == -1:
                            last_buy_closed[symbol] = virtual_close(position, history[-1]['Time'],
                                                                    history[-1]['Open'])
                            virtual_buys[symbol].remove(position)
                        else:
                            market.close(data_time, history[-1]['Open'], position['Volume'], position['Ticket'])

        open_sell_poses = copy.deepcopy(market.open_sell_positions) + virtual_sells[symbol]
        for position in open_sell_poses:
            if position['Symbol'] == symbol:
                entry_point = Outputs.index_date_v2(trailing_histories[symbol],
                                                    position['start_gmt'])
                is_close, close_price = trailing_tool.on_tick(trailing_histories[symbol],
                                                              entry_point, 'sell', data_time)
                if is_close:
                    if history[-1]['Low'] <= close_price <= history[-1]['High']:
                        if position['Ticket'] == -1:
                            last_sell_closed[symbol] = virtual_close(position, history[-1]['Time'], close_price)
                            virtual_sells[symbol].remove(position)
                        else:
                            market.close(data_time, close_price, position['Volume'], position['Ticket'])
                    elif not config.force_close_on_algorithm_price and close_price < history[-1]['Open']:
                        if position['Ticket'] == -1:
                            last_sell_closed[symbol] = virtual_close(position, history[-1]['Time'],
                                                                     history[-1]['Open'])
                            virtual_sells[symbol].remove(position)
                        else:
                            market.close(data_time, history[-1]['Open'], position['Volume'], position['Ticket'])


def virtuals_check(virtual_buys, virtual_sells, history, last_buy_closed, last_sell_closed, symbol, spread):
    virtual_buys_copy = copy.copy(virtual_buys)
    for virtual_buy in virtual_buys_copy:
        if virtual_buy['stop_loss'] != 0 and history[-1]['Low'] <= virtual_buy['stop_loss']:
            last_buy_closed[symbol] = virtual_close(virtual_buy, history[-1]['Time'], virtual_buy['stop_loss'])
            virtual_buys.remove(virtual_buy)
        elif virtual_buy['take_profit'] != 0 and history[-1]['High'] >= virtual_buy['take_profit']:
            last_buy_closed[symbol] = virtual_close(virtual_buy, history[-1]['Time'], virtual_buy['take_profit'])
            virtual_buys.remove(virtual_buy)

    virtual_sells_copy = copy.copy(virtual_sells)
    for virtual_sell in virtual_sells_copy:
        if virtual_sell['stop_loss'] != 0 and history[-1]['High'] + spread >= virtual_sell['stop_loss']:
            last_sell_closed[symbol] = virtual_close(virtual_sell, history[-1]['Time'],
                                                     virtual_sell['stop_loss'] + spread)
            virtual_sells.remove(virtual_sell)
        elif virtual_sell['take_profit'] != 0 and history[-1]['low'] + spread <= virtual_sell['take_profit']:
            last_sell_closed[symbol] = virtual_close(virtual_sell, history[-1]['Time'], virtual_sell['take_profit'])
            virtual_sells.remove(virtual_sell)


def virtual_close(virtual_position, end_gmt, end_price):
    return {'start_gmt': virtual_position['start_gmt'],
            'start_price': virtual_position['start_price'],
            'end_gmt': end_gmt,
            'end_price': end_price, 'symbol': virtual_position['symbol'],
            'stop_loss': virtual_position['stop_loss'],
            'take_profit': virtual_position['take_profit'],
            'volume': virtual_position['volume'], 'ticket': virtual_position['ticket']}


def re_entrance(market, config, tp_sl_tool, close_modes, re_entrance_algorithm, history, algorithm_histories, data_time, buy_open_positions_lens, sell_open_positions_lens,
                last_buy_closed, last_sell_closed, last_algorithm_signal_ticket, price, take_profit_buy,
                stop_loss_buy, take_profit_sell, stop_loss_sell, trade_buy_in_candle_counts, trade_sell_in_candle_counts,
                virtual_buys, virtual_sells, volume, last_ticket, symbol):
    if config.re_entrance_enable:
        is_buy_closed, is_sell_closed = False, False
        start_index_position_buy, start_index_position_sell = 0, 0
        is_algorithm_signal = False
        profit_in_pip = 0
        if buy_open_positions_lens[symbol] > market.get_open_buy_positions_count(symbol) + len(
                virtual_buys[symbol]):
            is_buy_closed = True
            start_index_position_buy = Outputs.index_date_v2(algorithm_histories[symbol],
                                                             last_buy_closed[symbol]['start_gmt'])
            if start_index_position_buy == -1:
                start_index_position_buy = len(algorithm_histories[symbol]) - 1
            if last_buy_closed[symbol]['Ticket'] == last_algorithm_signal_ticket[symbol]:
                is_algorithm_signal = True
            position = last_buy_closed[symbol]
            profit_in_pip = (position['end_price'] - position['OpenPrice']) * 10 ** Config.symbols_pip[
                position['Symbol']] / 10
        if sell_open_positions_lens[symbol] > market.get_open_sell_positions_count(symbol) + len(
                virtual_sells[symbol]):
            is_sell_closed = True
            start_index_position_sell = Outputs.index_date_v2(algorithm_histories[symbol],
                                                              last_sell_closed[symbol]['start_gmt'])
            if start_index_position_sell == -1:
                start_index_position_sell = len(algorithm_histories[symbol]) - 1
            if last_sell_closed[symbol]['Ticket'] == last_algorithm_signal_ticket[symbol]:
                is_algorithm_signal = True
            position = last_sell_closed[symbol]
            profit_in_pip = (position['OpenPrice'] - position['end_price']) * 10 ** Config.symbols_pip[
                position['Symbol']] / 10

        signal_re_entrance, price_re_entrance = re_entrance_algorithm.on_tick(algorithm_histories[symbol],
                                                                              is_buy_closed, is_sell_closed,
                                                                              profit_in_pip,
                                                                              start_index_position_buy,
                                                                              start_index_position_sell,
                                                                              len(algorithm_histories[symbol]) - 1)

        if signal_re_entrance == 1 or signal_re_entrance == -1:
            take_profit, stop_loss, first_stop_loss, take_profit_buy, stop_loss_buy, take_profit_sell, \
            stop_loss_sell = tp_sl(close_modes, tp_sl_tool, algorithm_histories, signal_re_entrance, price, symbol)

        if take_profit_buy != 0:
            take_profit_buy += price_re_entrance - price
        if stop_loss_buy != 0:
            stop_loss_buy += price_re_entrance - price
        if take_profit_sell != 0:
            take_profit_sell += price_re_entrance - price
        if stop_loss_sell != 0:
            stop_loss_sell += price_re_entrance - price

        if signal_re_entrance == 1:  # re entrance buy signal
            if config.multi_position or (
                    not config.multi_position and market.get_open_buy_positions_count(symbol) == 0):
                if not config.enable_max_trade_per_candle or \
                        (config.enable_max_trade_per_candle and trade_buy_in_candle_counts[
                            symbol] < config.max_trade_per_candle):
                    if not config.force_re_entrance_price and price_re_entrance <= history[-1]['Open']:
                        market.buy(data_time, history[-1]['Open'], symbol, take_profit_buy, stop_loss_buy,
                                   volume, last_ticket)
                        last_ticket += 1
                        trade_buy_in_candle_counts[symbol] += 1
                        re_entrance_algorithm.reset_triggers('buy')
                    elif history[-1]['Low'] <= price_re_entrance <= history[-1]['High']:
                        market.buy(data_time, price_re_entrance, symbol, take_profit_buy, stop_loss_buy,
                                   volume, last_ticket)
                        last_ticket += 1
                        trade_buy_in_candle_counts[symbol] += 1
                        re_entrance_algorithm.reset_triggers('buy')
        elif signal_re_entrance == -1:  # re entrance sell signal
            if config.multi_position or (
                    not config.multi_position and market.get_open_sell_positions_count(symbol) == 0):
                if not config.enable_max_trade_per_candle or \
                        (config.enable_max_trade_per_candle and trade_sell_in_candle_counts[
                            symbol] < config.max_trade_per_candle):
                    if not config.force_re_entrance_price and price_re_entrance >= history[-1]['Open']:
                        market.sell(data_time, history[-1]['Open'], symbol, take_profit_sell, stop_loss_sell,
                                    volume, last_ticket)
                        last_ticket += 1
                        trade_sell_in_candle_counts[symbol] += 1
                        re_entrance_algorithm.reset_triggers('sell')
                    elif history[-1]['Low'] <= price_re_entrance <= history[-1]['High']:
                        market.sell(data_time, price_re_entrance, symbol, take_profit_sell, stop_loss_sell,
                                    volume, last_ticket)
                        last_ticket += 1
                        trade_sell_in_candle_counts[symbol] += 1
                        re_entrance_algorithm.reset_triggers('sell')

        buy_open_positions_lens[symbol] = market.get_open_buy_positions_count(symbol) + len(virtual_buys[symbol])
        sell_open_positions_lens[symbol] = market.get_open_sell_positions_count(symbol) + len(virtual_sells[symbol])
    return last_ticket


def recovery():
    pass



# Output Section
market = launch()
Simulation.get_output(market)
