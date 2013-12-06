#coding: utf-8
from datetime import datetime
import time

import api
from config import btc_accounts


bc = api.BTCChina()

DETECT_GAP = 10 #请求失败延迟时间

btc_balance = {} #账户btc余额
bc_clients = {}
cny_balance = {} #账户人民币余额

current_price = 0  #当前单价
initial_value = 0  #最初价钱
initial_time = datetime.now()
last_update_time = initial_time

LITTLE_CHANGE = 0.002  #涨幅阀值
MEDIUM_CHANGE = 0.005
HIGH_CHANGE = 0.01
MAX_CHANGE = 0.015

MIN_CHANGE_RATE = 0.05  #每次出货进货百分比
LITTLE_CHANGE_RATE = 0.1
MEDIUM_CHANGE_RATE = 0.15
HIGH_CHANGE_RATE = 0.3



def log(txt, level='info'):
    f = file('log.txt', 'a+')
    content = '%s:%s' % (str(datetime.now()), txt)
    if level != 'info':
        log(content)
    f.write(content + "\n")
    f.close()


def update_balance():
    """
    接收账户余额信息
    """
    global btc_balance, cny_balance
    for name in bc_clients:
        temp_bc = bc_clients[name]
        try:
            account_info = temp_bc.get_account_info()
        except:
            account_info = None
        if account_info:
            temp_btc_balance = account_info['balance']['btc']
            temp_btc_balance['amount'] = float(temp_btc_balance['amount'])
            temp_cny_balance = account_info['balance']['cny']
            temp_cny_balance['amount'] = float(temp_cny_balance['amount'])
            btc_balance[name] = temp_btc_balance
            cny_balance[name] = temp_cny_balance


def calculate_value():
    """
    账户总资产
    """
    all_value = {}

    for name in bc_clients:
        if current_price:
            all_value[name] = btc_balance[name]['amount'] * current_price + cny_balance[name]['amount']
        else:
            all_value[name] = cny_balance[name]['amount']
    return  all_value

def legal_number(num):
    return "%.4f" % num


def buy(percent, price):
    for name in bc_clients:
        temp_bc = bc_clients[name]
        btc_amount = cny_balance[name]['amount'] * percent / price
        log("[buy]%s,%f,%f" % (name, btc_amount, price), 'warning')
        try:
            temp_bc.buy(legal_number(price), legal_number(btc_amount))
        except:
            pass
        return


def sell(percent, price):
    for name in bc_clients:
        temp_bc = bc_clients[name]
        btc_amount = btc_balance[name]['amount'] * percent
        log("[sell]%s,%f,%f" % (name, btc_amount, price), 'warning')
        if btc_amount:
            try:
                temp_bc.sell(legal_number(price), legal_number(btc_amount))
            except:
                pass


def cancel_current_orders():
     for name in bc_clients:
        temp_bc = bc_clients[name]
        try:
            orders = temp_bc.get_orders()
        except:
            orders = {'order': []}
        now = time.time()
        for order in orders['order']:
            if now - order['date'] > 60:
                _id = order['id']
                log("cancel order:%s" % _id)
                temp_bc.cancel(_id)


def get_price_from_depth():
    """
    获取当前价格
    """
    depth = bc.get_market_depth()
    total = 0
    amount = 0
    for order in depth['market_depth']['ask']:
        total += order['price'] * order['amount']
        amount += order['amount']
    price = total / amount
    log(price)
    return price


def triple_step_buy_increase():
    global current_price, last_update_time
    count = 0
    price_list = []
    float_minute = []
    float_quarter = []
    float_hour = []
    old_price = 0
    old_price_quarter = 0
    while True:
        try:
            current_price = get_price_from_depth()
            log(current_price)
        except:
            log("get price failed")
            time.sleep(DETECT_GAP)
            continue
        price_list.append(current_price)
        count += 1
        # 1分钟操作 ==================================================
        if old_price:
            last_float = (current_price - old_price) / old_price
            float_minute.append(last_float)
            if float_minute.__len__() == 4:
                del float_minute[0]
            if float_minute.__len__() == 3:
                if float_minute[0] > 0 and float_minute[1] > 0 and last_float > 0:
                    if float_minute[0] + float_minute[1] + last_float > HIGH_CHANGE * 3:
                        buy(HIGH_CHANGE_RATE * 3, current_price + 60)
                    elif float_minute[0] + float_minute[1] + last_float > MEDIUM_CHANGE * 3:
                        buy(MEDIUM_CHANGE_RATE * 3, current_price + 20)
                    elif float_minute[0] + float_minute[1] + last_float > LITTLE_CHANGE * 3:
                        buy(LITTLE_CHANGE_RATE * 3, current_price + 5)
                    else:
                        buy(MIN_CHANGE_RATE, current_price + 3)
                elif float_minute[0] < 0 and float_minute[1] < 0 and last_float < 0:
                    if float_minute[0] + float_minute[1] + last_float < (0 - HIGH_CHANGE * 3):
                        sell(HIGH_CHANGE_RATE * 3, current_price - 60)
                    elif float_minute[0] + float_minute[1] + last_float < (0 - MEDIUM_CHANGE * 3):
                        sell(MEDIUM_CHANGE_RATE * 3, current_price - 20)
                    elif float_minute[0] + float_minute[1] + last_float < (0 - LITTLE_CHANGE * 3):
                        sell(LITTLE_CHANGE_RATE * 3, current_price - 5)
                    else:
                        sell(MIN_CHANGE_RATE, current_price - 3)
                else:
                    del float_minute[0]
                    del float_minute[1]
            if float_minute.__len__() == 2:
                if float_minute[0] > 0 and last_float > 0:
                    if float_minute[0] + last_float > HIGH_CHANGE * 2:
                        buy(HIGH_CHANGE_RATE * 2, current_price + 30)
                    elif float_minute[0] + last_float > MEDIUM_CHANGE * 2:
                        buy(MEDIUM_CHANGE_RATE * 2, current_price + 10)
                    elif float_minute[0] + last_float > LITTLE_CHANGE * 2:
                        buy(LITTLE_CHANGE_RATE * 2, current_price + 2)
                    else:
                        buy(MIN_CHANGE_RATE, current_price)
                elif float_minute[0] < 0 and last_float < 0:
                    if float_minute[0] + last_float < (0 - HIGH_CHANGE * 2):
                        sell(HIGH_CHANGE_RATE * 2, current_price - 30)
                    elif float_minute[0] + last_float < (0 - MEDIUM_CHANGE * 2):
                        sell(MEDIUM_CHANGE_RATE * 2, current_price - 10)
                    elif float_minute[0] + last_float < (0 - LITTLE_CHANGE * 2):
                        sell(LITTLE_CHANGE_RATE * 2, current_price - 2)
                    else:
                        sell(MIN_CHANGE_RATE, current_price)
                else:
                    del float_minute[0]
            if float_minute.__len__() == 1:
                if last_float > 0:
                    if last_float > MAX_CHANGE:
                        buy(HIGH_CHANGE_RATE, current_price + 10)
                    else:
                        if last_float > MEDIUM_CHANGE:
                            buy(MEDIUM_CHANGE_RATE, current_price + 3)
                if last_float < 0:
                    if last_float < (0 - MAX_CHANGE):
                        sell(HIGH_CHANGE_RATE, current_price - 10)
                    else:
                        if last_float < (0 - MEDIUM_CHANGE):
                            sell(MEDIUM_CHANGE_RATE, current_price - 3)
        old_price = current_price
        if count == 1:
            old_price_quarter = current_price
            old_price_hour = current_price
        # 15分钟操作 ==================================================
        if count % 15 == 0:
            last_float_quarter = (current_price - old_price_quarter) / old_price_quarter
            float_quarter.append(last_float_quarter)
            if float_quarter.__len__() == 4:
                del float_quarter[0]
            if float_quarter.__len__() == 3:
                if float_quarter[0] > 0 and float_quarter[1] > 0 and last_float > 0:
                    buy(HIGH_CHANGE_RATE, current_price + 10)
            old_price_quarter = current_price
        # 12小时操作操作 ==================================================
        if count == 720:
            last_float_hour = (current_price - old_price_hour) / old_price_hour
            float_hour.append(last_float_hour)
            if float_hour.__len__() == 7:
                del float_hour[0]
            if float_hour.__len__() == 6:
                if float_hour[0] > 0 and float_hour[1] > 0 and float_hour[2] > 0 and float_hour[3] > 0 and float_hour[
                    4] > 0 and last_float > 0:
                    sell(HIGH_CHANGE_RATE * 2, current_price - 5)
            old_price_quarter = current_price
            count == 0
        cancel_current_orders()
        update_balance()
        time.sleep(60)


def init_bcclients():
    global bc_clients
    bc_clients = {}
    for name in btc_accounts:
        account = btc_accounts[name]
        bc_clients[name] = api.BTCChina(account['access_key'], account['secret_key'])


if __name__ == "__main__":
    init_bcclients()
    update_balance()
    current_price = get_price_from_depth()
    # initial_value = calculate_value()
    # log("[begin]now the value is %f" % initial_value, 'warning')
    triple_step_buy_increase()
