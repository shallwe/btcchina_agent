#coding: utf-8
from datetime import datetime, timedelta
import time

import api


bc = api.BTCChina()

PRICE_LENGTH = 30
SINGLE_THRESHOLD_CHANGE = 0.002
MULTI_THRESHOLD_CHANGE = 0.01
LITTLE_CHANGE_RATE = 0.1#每次出货进货的量
MEDIUM_CHANGE_RATE = 0.2#每次出货进货的量
HIGH_CHANGE_RATE = 0.3#每次出货进货的量
DETECT_GAP = 5

btc_balance = {}
cny_balance = {}
current_value = 0  #当前价值
price_history = [] #价格历史
history_change = [] #历史上的变动

current_price = 0
current_value = 0
initial_value = 0 #最初价钱
initial_time = datetime.now()
last_update_time = initial_time


def log(txt, level='info'):
    f = file('log.txt', 'a+')
    content = '%s:%s' % (str(datetime.now()), txt)
    if level != 'info':
        print content
    f.write(content + "\n")
    f.close()


def update_balance():
    global btc_balance, cny_balance
    try:
        account_info = bc.get_account_info()
    except:
        account_info = None
    if account_info:
        btc_balance = account_info['balance']['btc']
        btc_balance['amount'] = float(btc_balance['amount'])
        cny_balance = account_info['balance']['cny']
        cny_balance['amount'] = float(cny_balance['amount'])


def calculate_value():
    if current_price:
        return btc_balance['amount'] * current_price + cny_balance['amount']
    else:
        return cny_balance['amount']

def legal_number(num):
    return "%.4f" % num


def buy(percent, price):
    btc_amount = cny_balance['amount'] * percent / price
    log("[sell]%f,%f" % (btc_amount, price), 'warning')
    try:
        bc.buy(legal_number(price), legal_number(btc_amount))
    except:
        pass
    return


def sell(percent, price):
    btc_amount = btc_balance['amount'] * percent
    log("[sell]%f,%f" % (btc_amount, price), 'warning')
    if btc_amount:
        try:
            bc.sell(legal_number(price), legal_number(btc_amount))
        except:
            pass


def cancel_current_orders():
    orders = bc.get_orders()
    now = time.time()
    for order in orders['order']:
        if now - order['date'] > 300:
            _id = order['id']
            log("cancel order:%s" % _id)
            bc.cancel(_id)


def get_price_from_depth():
    depth = bc.get_market_depth()
    total = 0
    amount = 0
    for order in depth['market_depth']['ask']:
        total += order['price'] * order['amount']
        amount += order['amount']
    price =  total / amount
    log(price)
    return price


def append_price(price):
    global price_history
    if len(price_history) < PRICE_LENGTH:
        price_history.append(price)
    else:
        price_history = price_history[1:]
        price_history.append(price)


def append_change_history(change):
    global history_change
    if len(history_change) < 10:
        history_change.append(change)
    else:
        history_change = history_change[1:]
        history_change.append(change)

def multi_change():
    result = 1
    for change in history_change:
        result *= change
    return  result

def is_decreasing():
    if len(price_history) > PRICE_LENGTH / 5:
        total = 0
        count = PRICE_LENGTH/10
        for i in xrange(count):
            total += price_history[i]
        old_price = total / count
        if current_price < old_price:
            if (-1 * calculate_delta_rate(old_price, current_price)) > SINGLE_THRESHOLD_CHANGE:
                return True
    return False


def is_increasing():
    if len(price_history) > PRICE_LENGTH / 5:
        total = 0
        count = PRICE_LENGTH/10
        for i in xrange(count):
            total += price_history[i]
        old_price = total / count
        if current_price > old_price:
            if calculate_delta_rate(old_price, current_price) > SINGLE_THRESHOLD_CHANGE:
                return True
    return False


def calculate_delta_rate(old_val, new_val):
    delta = new_val - old_val
    return delta / old_val


def buy_decrease():
    global current_price, last_update_time, current_value
    while True:
        try:
            current_price = get_price_from_depth()
        except:
            log('get price fail', 'warning')
            time.sleep(10)
            continue
        append_price(current_price)
        if is_decreasing():
            log("[decrease]buy", 'warning')
            update_balance()
            buy(LITTLE_CHANGE_RATE, current_price)
        elif is_increasing():
            log("[increase]sell", 'warning')
            update_balance()
            sell(LITTLE_CHANGE_RATE, current_price)
        else:
            log("nothing", 'warning')
        if datetime.now() - last_update_time > timedelta(hours=0.5):
            cancel_current_orders()
            update_balance()
            current_value = calculate_value()
            log("[effect]current the rate is %f" % calculate_delta_rate(initial_value, current_value), 'warning')
            last_update_time = datetime.now()
        time.sleep(10)


def buy_increase():
    global current_price, last_update_time, current_value
    while True:
        try:
            current_price = get_price_from_depth()
        except:
            time.sleep(10)
            continue
        append_price(current_price)
        if is_decreasing():
            log("[decrease]sell", 'warning')
            update_balance()
            sell(LITTLE_CHANGE_RATE, current_price)
        elif is_increasing():
            log("[increase]buy", 'warning')
            update_balance()
            buy(LITTLE_CHANGE_RATE, current_price)
        else:
            log("nothing", 'warning')
        if datetime.now() - last_update_time > timedelta(hours=0.5):
            cancel_current_orders()
            update_balance()
            current_value = calculate_value()
            log("[effect]current the rate is %f" % calculate_delta_rate(initial_value, current_value), 'warning')
            last_update_time = datetime.now()
        time.sleep(5)


def triple_step_buy_increase():
    global current_price, last_update_time, current_value
    count = 0
    price_list = []
    old_price = 0
    while True:
        try:
            current_price = get_price_from_depth()
        except:
            log("get price failed")
            time.sleep(DETECT_GAP)
            continue
        price_list.append(current_price)
        count += 1
        if count % 3 == 0:
            avg_price = (price_list[0] + price_list[1] + price_list[2]) / 3
            price_list = []
            log("average_price: %.4f" % avg_price, 'warning')
            if old_price != 0:
                change_rate = avg_price / old_price
                append_change_history(change_rate)
                total_change = multi_change()
                print "change:%f, multichange:%f" % (change_rate, total_change)
                if change_rate > 1 + SINGLE_THRESHOLD_CHANGE or change_rate < 1 - SINGLE_THRESHOLD_CHANGE or \
                                total_change > 1 + MULTI_THRESHOLD_CHANGE or total_change < 1 - MULTI_THRESHOLD_CHANGE:
                    update_balance()
                if change_rate > 1 + SINGLE_THRESHOLD_CHANGE:
                    if total_change > 1 + MULTI_THRESHOLD_CHANGE:
                        buy(LITTLE_CHANGE_RATE, current_price)
                    elif total_change < 1 - MULTI_THRESHOLD_CHANGE:
                        buy(HIGH_CHANGE_RATE, current_price)
                    else:
                        buy(MEDIUM_CHANGE_RATE, current_price)
                elif change_rate < 1 - SINGLE_THRESHOLD_CHANGE:
                    if total_change > 1 + MULTI_THRESHOLD_CHANGE:
                        sell(HIGH_CHANGE_RATE, current_price)
                    elif total_change < 1 - MULTI_THRESHOLD_CHANGE:
                        buy(LITTLE_CHANGE_RATE, current_price)
                    else:
                        buy(MEDIUM_CHANGE_RATE, current_price)
                else:
                    if total_change > 1 + MULTI_THRESHOLD_CHANGE:
                        sell(LITTLE_CHANGE_RATE, current_price)
                    elif total_change < 1 - MULTI_THRESHOLD_CHANGE:
                        buy(LITTLE_CHANGE_RATE, current_price)
                    else:
                        log("nothing todo")
            old_price = avg_price
            if datetime.now() - last_update_time > timedelta(hours=0.5):
                cancel_current_orders()
                update_balance()
                current_value = calculate_value()
                log("[effect]current the rate is %f" % calculate_delta_rate(initial_value, current_value), 'warning')
                last_update_time = datetime.now()
        time.sleep(5)


if __name__ == "__main__":
    update_balance()
    current_price = get_price_from_depth()
    initial_value = calculate_value()
    log("[begin]now the value is %f" % initial_value, 'warning')
    triple_step_buy_increase()
