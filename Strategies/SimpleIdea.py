
from Strategies.Strategy import Strategy

from AlgorithmFactory.AlgorithmPackages.SimpleIdea.SimpleIdeaPkg import simple_idea
from Shared.Variables import Variables
from AlgorithmFactory.AlgorithmTools.LocalExtermums import *


class SimpleIdea(Strategy):

    def __init__(self, market, data, symbol,  win_inc, win_dec, shadow_threshold, body_threshold, mode, mean_window, extremum_window, extremum_mode, alpha, impulse_threshold):
        super().__init__(market, data)
        self.symbol = symbol
        self.win_inc = win_inc
        self.win_dec = win_dec
        self.mode = mode
        self.mean_window = mean_window
        self.window_size = max(win_inc, win_dec)
        self.symbol = symbol
        self.shadow_threshold = shadow_threshold
        self.body_threshold = body_threshold
        self.extremum_window = extremum_window
        self.extremum_mode = extremum_mode
        self.alpha = alpha
        self.impulse_threshold = impulse_threshold * 10 ** -Variables.config.symbols_pip[symbol]
        len_window = len(data)
        if len_window <= self.window_size:
            raise Exception("window len should be greater than window size")
        self.local_min_price, self.local_max_price = get_local_extermums(self.data, self.extremum_window,
                                                                         self.extremum_mode)

    def on_tick(self):
        pass

    def on_data(self, candle):
        self.data.pop(0)

        signal = simple_idea(self.symbol, self.data, self.win_inc, self.win_dec, self.shadow_threshold, self.body_threshold,
                    self.mode, self.mean_window)

        if signal == 1:
            self.market.buy(candle['Close'], self.symbol, 400, 400, 0.1)
        elif signal == -1:
            self.market.sell(candle['Close'], self.symbol, 400, 400, 0.1)

        self.data.append(candle)
