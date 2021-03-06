#!/usr/bin/python

#######################################################
#                                                     #
#  Copyright Masterchain Grazcoin Grimentz 2013-2014  #
#  https://github.com/grazcoin/mastercoin-tools       #
#  https://masterchain.info                           #
#  masterchain@@bitmessage.ch                         #
#  License AGPLv3                                     #
#                                                     #
#######################################################

import os
import sys
from optparse import OptionParser
from msc_utils_validating import *

# alarm to release funds if accept not paid on time
# format is {block:[accept_tx1, accept_tx2, ..], ..}
alarm={}

# create address dict that holds all details per address
addr_dict={}
tx_dict={}

#create dict of active fundraisers
fundraisers_dict={}
fundraisers_metadata_dict={}
#create dict of divisible/non smart_properties
property_type_dict={}
# invalidate tx due to "avoid changing history" issues
#invalidate_tx_list=['13fb62038d98ca4680c6295ba10d17b63c050ccde9c4cee7579fd2e148f25581', \
#                    '67d6302a45380289de0097afdae8d21a84b0a41221ca14319b3e4cdd8952a53b', \
#                    '8593540888247a9772fbe0fbcdd765df179779ae0c728e1fe83051f1bf0efe2f']

# prepare lists for mastercoin and test
sorted_currency_tx_list={'Mastercoin':[],'Test Mastercoin':[]} # list 0 for mastercoins, list 1 for test mastercoins
sorted_currency_sell_tx_list={'Mastercoin':[],'Test Mastercoin':[]} # list 0 for mastercoins, list 1 for test mastercoins
sorted_currency_accept_tx_list={'Mastercoin':[],'Test Mastercoin':[]} # list 0 for mastercoins, list 1 for test mastercoins
sorted_currency_sell_tx_list={'Mastercoin':[],'Test Mastercoin':[]} # list 0 for mastercoins, list 1 for test mastercoins
filtered_tx_list={'Mastercoin':[],'Test Mastercoin':[]} # list 0 for mastercoins, list 1 for test mastercoins

# all available properties of a transaction
tx_properties=\
    ['tx_hash', 'invalid', 'tx_time', \
     'amount', 'formatted_amount', \
     'from_address', 'to_address', 'transactionType', \
     'icon', 'icon_text', 'color', \
     'block', 'index', \
     'details', 'tx_type_str', \
     'baseCoin', 'dataSequenceNum', 'method', 'tx_method_str', \
     'bitcoin_amount_desired', 'block_time_limit', 'fee', \
     'sell_offer_txid', 'accept_txid', 'btc_offer_txid', \
     'prev_payment_txid', 'next_payment_txid', 'accomulated_payment', \
     'action', 'action_str', \
     'amount_available', 'formatted_amount_available', \
     'formatted_amount_accepted', 'formatted_amount_bought', \
     'formatted_amount_requested', 'formatted_price_per_coin', 'bitcoin_required', \
     'payment_done', 'payment_expired', \
     'updating', 'updated_by', \
     'status','fundraiser_send']

# all available properties of a currency in address
addr_properties=['balance', 'reserved', 'received', 'sent', 'bought', 'sold', 'offer', 'accept', 'reward',\
            'in_tx', 'out_tx', 'bought_tx', 'sold_tx', 'offer_tx', 'accept_tx', 'exodus_tx']

# coins and their numbers
coins_list=['Mastercoin', 'Test Mastercoin']
coins_dict={'Mastercoin':'0','Test Mastercoin':'1'}
coins_short_name_dict={'Mastercoin':'MSC','Test Mastercoin':'TMSC'}
coins_reverse_short_name_dict=dict((v,k) for k, v in coins_short_name_dict.iteritems())

# create modified tx dict which would be used to modify tx files
offers_dict={}

# create a property dict
properties_dict={}

# global last block on the net
last_height=get_last_height()

def sorted_ls(path):
    mtime = lambda f: os.stat(os.path.join(path, f)).st_mtime
    return list(sorted(os.listdir(path), key=mtime))

def initial_tx_dict_load():
    # run on all files in tx
    tx_files=sorted_ls('tx')

    # load dict of each
    for filename in tx_files:
        if filename.endswith('.json'):
            tx_hash=filename.split('.')[0]
            update_tx_dict(tx_hash)

def get_sorted_tx_list():
    # run on all files in tx
    tx_files=sorted_ls('tx')

    # load dict of each
    tx_list=[]
    for k in tx_dict.keys():
        tx_list+=tx_dict[k] # append the list of tx for each key (incl. exodus)
    # sort according to time
    return sorted(tx_list, key=lambda k: (int(k['block']),int(k['index']))) 

def add_alarm(tx_hash):
    t=tx_dict[tx_hash][-1] # last tx on the list
    tx_block=int(t['block'])
    sell_offer_txid=t['sell_offer_txid']
    sell_offer_tx=tx_dict[sell_offer_txid][-1]
    payment_timeframe=int(sell_offer_tx['formatted_block_time_limit'])
    alarm_block=tx_block+payment_timeframe
    if alarm.has_key(alarm_block):
        alarm[alarm_block].append(t)
        debug('added alarm in block '+str(alarm_block)+' for '+tx_hash)
    else:
        alarm[alarm_block]=[t]
        debug('added first alarm in block '+str(alarm_block)+' for '+tx_hash)

def remove_alarm(tx_hash):
    t=tx_dict[tx_hash][-1] # last tx on the list
    tx_block=int(t['block'])
    sell_offer_txid=t['sell_offer_txid']
    sell_offer_tx=tx_dict[sell_offer_txid][-1]
    payment_timeframe=int(sell_offer_tx['formatted_block_time_limit'])
    alarm_block=tx_block+payment_timeframe
    if alarm.has_key(alarm_block):
        try:
            alarm[alarm_block].remove(t)
            debug('removed alarm at block '+str(alarm_block)+' for '+tx_hash)
        except ValueError:
            info('failed removing alarm for '+tx_hash)
    else:
        info('failed removing alarm for '+tx_hash+' since no alarm block '+alarm_block)

def check_alarm(t, last_block, current_block):
    # check alarms for all blocks since last check
    # if late - mark expired
    for b in range(last_block, current_block):
        if alarm.has_key(b):
            debug('alarm for block '+str(b))
            debug('transaction checked in alarm for block are '+str(alarm[b]))
            for a in alarm[b]:
                debug('verify payment for tx '+str(a['tx_hash']))
                tx_hash=a['tx_hash']
                amount=float(a['formatted_amount'])
                amount_accepted=float(a['formatted_amount_accepted'])
                amount_bought=float(a['formatted_amount_bought'])

                # not paid case
                if not a.has_key('btc_offer_txid') or a['btc_offer_txid']=='unknown': # accept with no payment
                    # update accept transaction with expired note
                    debug('accept offer expired '+tx_hash)
                    update_tx_dict(tx_hash, payment_expired=True, color='bgc-expired', \
                        icon_text='Payment expired', formatted_amount_bought='0.0', status='Expired')

                    # update the sell side for expired payment
                    if a.has_key('sell_offer_txid'):
                        # get sell transaction details
                        sell_tx_hash=a['sell_offer_txid']
                        sell_tx=tx_dict[sell_tx_hash][-1]

                        amount_available=float(sell_tx['formatted_amount_available'])
                        # amount available grows when an accept expires
                        updated_amount_available=float(amount_available)+float(amount_accepted)
                        formatted_updated_amount_available=formatted_decimal(updated_amount_available)
                        debug('update sell transaction '+sell_tx_hash+' and address '+sell_tx['from_address']+ \
                            ' with amount available '+str(updated_amount_available)+' after payment expired')
                        # update sell transaction - amount_available increases
                        update_tx_dict(sell_tx_hash, amount_available=updated_amount_available, \
                            formatted_amount_available=formatted_updated_amount_available)

                        # check if sell offer got updated for later updates
                        try:
                            sell_tx_updated_by=sell_tx['updated_by']
                            if sell_tx_updated_by == None or sell_tx_updated_by == 'unknown':
                                sell_tx_updated=False
                            else:
                                sell_tx_updated=True
                        except KeyError:
                            sell_tx_updated=False

                        # heavy debug
                        debug_address(a['from_address'], a['currency_str'], 'before alarm expired')
                        debug_address(a['to_address'], a['currency_str'], 'before alarm expired')

                        # update buyer address - accept decreases
                        update_addr_dict(a['from_address'], True, a['currency_str'], accept=-to_satoshi(amount_accepted))

                        # if sell offer got updated during the accept, drop the reserved due to that accept
                        current_sell_tx=addr_dict[a['to_address']][a['currency_str']]['offer_tx'][-1]
                        if sell_tx['tx_hash'] != current_sell_tx['tx_hash']:
                            # update seller address - offer change isn't relevant to current sell offer.
                            # reserved moves to balance.

                            # but only if sell tx did not get upated
                            if not sell_tx_updated:
                                update_addr_dict(a['to_address'], True, a['currency_str'], reserved=-to_satoshi(amount_accepted), \
                                    balance=to_satoshi(amount_accepted))
                            else:
                                update_addr_dict(a['to_address'], True, a['currency_str'], balance=to_satoshi(amount_accepted))
                                debug('skip updating reserved on '+a['to_address']+' as payment expired and it got already updated')
                        else:
                            # update seller address - offer increases (reserved stays)
                            update_addr_dict(a['to_address'], True, a['currency_str'], offer=to_satoshi(amount_accepted))

                        # heavy debug
                        debug_address(a['from_address'], a['currency_str'], 'after alarm expired')
                        debug_address(a['to_address'], a['currency_str'], 'after alarm expired')

                        # update icon colors of sell
                        try:
                            # depracated
                            if sell_tx['updated_by'] != None:
                                update_tx_dict(sell_tx['tx_hash'], icon_text='Depracated sell offer', color='bgc-expired')
                        except KeyError:
                            # back to new
                            if updated_amount_available == amount:
                                update_tx_dict(sell_tx['tx_hash'], color='bgc-new', icon_text='Sell offer')
                            else:
                                if updated_amount_available == 0:
                                    # fully accepted
                                    update_tx_dict(sell_tx['tx_hash'], color='bgc-accepted', icon_text='Sell offer accepted')
                                else:
                                    # partially accepted
                                    update_tx_dict(sell_tx['tx_hash'], color='bgc-new-accepted', icon_text='Sell offer partially accepted')
                    else:
                        info('BUG: remove alarm for accept without sell_offer_txid '+a['tx_hash'])
                    # no need to check this accept any more, but leave on alarms dict
                    debug('checked alarm for expired '+tx_hash)
                else:
                    debug('accept offer '+tx_hash+' was already paid with '+a['btc_offer_txid'])
                    # update left over accept on buyer side
                    left_over_accept=amount_accepted-amount_bought
                    debug('reduce left over accept from buyer accept value due to accept expire of '+tx_hash)
                    update_addr_dict(a['from_address'], True, a['currency_str'], accept=-to_satoshi(left_over_accept))
 


def check_bitcoin_payment(t):
    if t['invalid']==[True, 'bitcoin payment']:
        from_address=t['from_address']
        if from_address.find(';') >= 0: # there are multiple inputs
            from_address=from_address.split(';')[0] # take the first one
        current_block=int(t['block'])
        # was there accept from this address to any of the payment addresses?
        to_multi_address_and_amount=t['to_address'].split(';')
        for address_and_amount in to_multi_address_and_amount:
            (address,amount)=address_and_amount.split(':')
            if address!=exodus_address:
                debug('is that a '+amount+' payment to '+address+' ?')
                # check if it fits to a sell offer in address
                # first check if msc sell offer exists
                sell_offer_tx=None
                sell_accept_tx=None
                required_btc=0
                for c in coins_list: # check for offers of Mastercoin or Test Mastercoin
                    try:
                        sell_offer_tx_list=addr_dict[address][c]['offer_tx']
                    except (IndexError,KeyError):
                        sell_offer_tx_list=[]
                    reversed_sell_offer_tx_list=list(reversed(sell_offer_tx_list))
                    for sell_offer_tx in reversed_sell_offer_tx_list:
                        # any relevant sell offer found?
                        if sell_offer_tx != None:
                            debug('found! checking:')
                            debug('bitcoin payment: '+t['tx_hash'])
                            debug('for sell offer: '+sell_offer_tx['tx_hash'])

                            try:
                                required_btc=float(sell_offer_tx['formatted_bitcoin_amount_desired'])
                                whole_sell_amount=float(sell_offer_tx['formatted_amount'])
                                amount_available=float(sell_offer_tx['formatted_amount_available'])
                                block_time_limit=int(sell_offer_tx['formatted_block_time_limit'])
                            except KeyError:
                                info('BUG: sell offer with missing details: '+sell_offer_tx['tx_hash'])
                                continue

                            # get the reserved on the sell address
                            amount_reserved=from_satoshi(addr_dict[address][c]['reserved'])

                            # now find the relevant accept and verify details (also partial purchase)
                            try:
                                sell_accept_tx_list=addr_dict[from_address][c]['accept_tx']
                            except KeyError:
                                debug('no accept_tx on '+from_address)
                                continue
                            debug('run over sell accept list ...')
                            for sell_accept_tx in sell_accept_tx_list: # go over all accepts
                                debug('... check accept '+sell_accept_tx['tx_hash'])
                                sell_offer_accepted=sell_accept_tx['sell_offer_txid']
                                if sell_offer_accepted != sell_offer_tx['tx_hash']:
                                    debug('... sell accept is for a different sell offer ('+sell_offer_accepted+')')
                                    continue

                                accept_buyer=sell_accept_tx['from_address']
                                payment_sender=from_address
                                if payment_sender != accept_buyer:
                                    debug('not correct accept since payment sender and accept buyer are different')
                                    continue

                                accept_seller=sell_accept_tx['to_address']
                                sell_seller=sell_offer_tx['from_address']
                                if accept_seller != sell_seller:
                                    debug('not correct accept since accept seller and sell offer seller are different')
                                    continue

                                # calculate the amount accepted
                                try:
                                    amount_accepted=float(sell_accept_tx['formatted_amount_accepted'])
                                except KeyError:
                                    info('BUG: continue to next accept, since no formatted_amount_accepted on '+sell_accept_tx['tx_hash'])
                                    # this was not the right accept
                                    continue

                                # get the amount bought
                                try:
                                    amount_bought=float(sell_accept_tx['formatted_amount_bought'])
                                except KeyError:
                                    amount_bought=0.0

                                # is accept exhausted?
                                if amount_accepted == amount_bought:
                                    debug('... skip this accept since it is already fully paid '+sell_accept_tx['tx_hash'])
                                    continue

                                # now check if block time limit is as required
                                sell_accept_block=int(sell_accept_tx['block'])

                                # if sell accept is valid, then fee is OK - no need to re-check
                                if sell_accept_block+block_time_limit >= current_block:
                                    debug('... payment timing fits ('+str(sell_accept_block)+'+'+str(block_time_limit)+' >= '+str(current_block)+')')

                                    # heavy debug
                                    debug_address(address, c, 'before bitcoin payment')
                                    debug_address(from_address, c, 'before bitcoin payment')

                                    accomulated_payment=0
                                    payments_list=[]
                                    # check if accept got already paid
                                    btc_offer_txid=None
                                    try:
                                        btc_offer_txid=sell_accept_tx['btc_offer_txid']
                                    except KeyError:
                                        pass

                                    debug(btc_offer_txid)

                                    # was there already a payment?
                                    if btc_offer_txid != None and btc_offer_txid != 'unknown':
                                        # there was at least one payment
                                        # let's chain this payment to previous payments
                                        # build the chain of payments
                                        debug('build the chain of payments')
                                        payments_list.append(btc_offer_txid)
                                        # get/set accomulated payment
                                        try:
                                            accomulated_payment=tx_dict[btc_offer_txid][-1]['accomulated_payment']
                                        except (KeyError, IndexError):
                                            # if not accomulated_payment field on btc_offer_txid, then it is the first
                                            info('BUG: no accomulated amount on first bitcoin payment for accept '+sell_accept_tx['tx_hash']+' on '+btc_offer_txid)
                                            break

                                        # running until this payment is in the payments list
                                        while payments_list[-1] != t['tx_hash']:
                                            # take care with endless loop here
                                            # is this payment the last, or are there other previous payments?
                                            next_payment_txid=None
                                            try:
                                                next_payment_txid=tx_dict[payments_list[-1]][-1]['next_payment_txid']
                                            except (KeyError,IndexError):
                                                pass

                                            if next_payment_txid == None or next_payment_txid == 'unknwon':
                                                # This payment is the last one.
                                                # connect it to the chain of payments.
                                                next_payment_txid=t['tx_hash']
                                                debug('adding payment '+next_payment_txid+' to payment chain for accept '+sell_accept_tx['tx_hash'])
                                                payments_list.append(next_payment_txid)
                                                if payments_list[-2] == payments_list[-1]:
                                                    info('BUG: loop of payments on last payment in accept '+sell_accept_tx['tx_hash']+'. First is '+btc_offer_txid+' and additional is '+t['tx_hash'])
                                                    break
                                                debug('update payment '+payments_list[-2]+' with next payment '+payments_list[-1])
                                                update_tx_dict(payments_list[-2], next_payment_txid=payments_list[-1])
                                                debug('update payment '+payments_list[-1]+' with prev payment '+payments_list[-2])
                                                update_tx_dict(payments_list[-1], prev_payment_txid=payments_list[-2])

                                                # calculate accomulated payment (sum of amounts of all payments for this accept)
                                                try:
                                                    accomulated_payment=float(tx_dict[payments_list[-2]][-1]['accomulated_payment'])+float(amount)
                                                except (KeyError, IndexError):
                                                    info('BUG: no accomulated amount on later bitcoin payment for accept '+sell_accept_tx['tx_hash']+' on '+payments_list[-2])
                                                    break
                                                debug('update accomulated payment to '+str(accomulated_payment))
                                                update_tx_dict(payments_list[-1], accomulated_payment=accomulated_payment)

                                            else:
                                                debug('add payment to the chain '+next_payment_txid)
                                                payments_list.append(next_payment_txid)
                                                # get stored accomulated payment (amount was added on previous run)
                                                try:
                                                    accomulated_payment=float(tx_dict[payments_list[-1]][-1]['accomulated_payment'])
                                                except (KeyError,IndexError):
                                                    info('BUG: no accomulated amount on stored bitcoin payment for accept '+sell_accept_tx['tx_hash']+' on '+payments_list[-1])

                                                # check for trivial loop, but there can be more complicated loops
                                                try:
                                                    if payments_list[-2] == payments_list[-1]:
                                                        info('BUG: loop of payments on accept '+sell_accept_tx['tx_hash']+'. First is '+btc_offer_txid+' and additional is '+t['tx_hash'])
                                                        break
                                                except IndexError:
                                                    pass

                                                # skip to the next payment on the chain
                                                continue
                                    else:
                                        # This is the first payment
                                        update_tx_dict(sell_accept_tx['tx_hash'], btc_offer_txid=t['tx_hash'])
                                        accomulated_payment=float(amount)
                                        update_tx_dict(t['tx_hash'], accomulated_payment=accomulated_payment)
                                        debug('first bitcoin payment '+t['tx_hash']+' for accept '+sell_accept_tx['tx_hash']+' is '+str(accomulated_payment))

                                    part_bought=float(accomulated_payment)/required_btc
                                    amount_closed=min((part_bought*float(whole_sell_amount)+0.0), amount_accepted, amount_reserved)
                                    debug('... amount_accepted is '+str(amount_accepted))
                                    debug('... amount_reserved is '+str(amount_reserved))
                                    debug('... amount_available is '+str(amount_available))
                                    debug('... amount_closed is '+str(amount_closed))

                                    if part_bought>0:
                                        # mark accept as closed if part bought is 100%

                                        if float(amount_closed) < 0:
                                            info('BUG: negative amount closed for accept '+sell_accept_tx['tx_hash'])

                                        if float(accomulated_payment) == float(amount): # first payment
                                            # update seller address - reserved decreases, balance stays, offer updates (decreased at accept).
                                            satoshi_amount_closed=to_satoshi(amount_closed)
                                            satoshi_amount_accepted=to_satoshi(amount_accepted)
                                            satoshi_amount_reserved=to_satoshi(amount_reserved)

                                            # keep reserved at least zero
                                            satoshi_reserved_update=min(satoshi_amount_closed, satoshi_amount_reserved)

                                            update_addr_dict(address, True, c, reserved=-satoshi_reserved_update, sold=satoshi_amount_closed, \
                                                sold_tx=sell_accept_tx, offer=-satoshi_amount_closed+satoshi_amount_accepted)

                                            # update buyer address - balance increases, accept decreases.
                                            update_addr_dict(from_address, True, c, accept=-satoshi_amount_closed, \
                                                balance=satoshi_amount_closed, bought=satoshi_amount_closed, bought_tx=t)

                                            # update sell available (less closed - accepted)
                                            updated_amount_available = float(amount_available) + float(amount_accepted) - float(amount_closed)

                                            if float(updated_amount_available) < 0:
                                                info('BUG: negative updated amount available after '+sell_accept_tx['tx_hash'])

                                            debug('... update sell offer amount available '+formatted_decimal(updated_amount_available)+' at '+sell_offer_tx['tx_hash'])
                                            update_tx_dict(sell_offer_tx['tx_hash'], amount_available=updated_amount_available, \
                                                formatted_amount_available=formatted_decimal(updated_amount_available))

                                            # update sell accept tx (with bitcoin payment etc)
                                            update_tx_dict(sell_accept_tx['tx_hash'], status='Closed', \
                                                payment_done=True, formatted_amount_bought=formatted_decimal(amount_closed),  \
                                                color='bgc-done', icon_text='Accept offer paid')

                                            # update sell and accept offer in bitcoin payment
                                            update_tx_dict(t['tx_hash'], sell_offer_txid=sell_offer_tx['tx_hash'], accept_txid=sell_accept_tx['tx_hash'])

                                            # update purchased amount on bitcoin payment
                                            update_tx_dict(t['tx_hash'], formatted_amount=formatted_decimal(amount_closed))
                                            
                                        else:
                                            # later payment
                                            debug('additional payment')
                                            additional_payment=amount
                                            additional_part=float(additional_payment)/required_btc
                                            prev_closed=min(((part_bought-additional_part)*float(whole_sell_amount)+0.0), amount_accepted, amount_reserved)
                                            diff_closed=amount_closed-prev_closed
                                            satoshi_diff_closed=to_satoshi(diff_closed)
                                            satoshi_amount_reserved=to_satoshi(amount_reserved)

                                            # keep reserved at least zero
                                            satoshi_reserved_update=min(satoshi_diff_closed, satoshi_amount_reserved)

                                            # update seller address
                                            update_addr_dict(address, True, c, reserved=-satoshi_reserved_update, sold=satoshi_diff_closed, \
                                                offer=-satoshi_diff_closed)

                                            # update buyer address - balance increases, accept decreases.
                                            update_addr_dict(from_address, True, c, accept=-satoshi_diff_closed, \
                                                balance=satoshi_diff_closed, bought=satoshi_diff_closed, bought_tx=t)

                                            # update sell available (less diff_closed)
                                            updated_amount_available = float(amount_available) - float(diff_closed)

                                            if float(updated_amount_available) < 0:
                                                info('BUG: negative updated amount available on later payment '+t['tx_hash'])

                                            debug('... update sell offer amount available '+formatted_decimal(updated_amount_available)+' at '+sell_offer_tx['tx_hash'])
                                            update_tx_dict(sell_offer_tx['tx_hash'], amount_available=updated_amount_available, \
                                                formatted_amount_available=formatted_decimal(updated_amount_available))

                                            # update sell accept tx (only amount bought changed)
                                            update_tx_dict(sell_accept_tx['tx_hash'], formatted_amount_bought=formatted_decimal(amount_closed))

                                            # update sell and accept offer in bitcoin payment
                                            update_tx_dict(t['tx_hash'], sell_offer_txid=sell_offer_tx['tx_hash'], accept_txid=sell_accept_tx['tx_hash'])

                                            # update purchased amount on bitcoin payment
                                            update_tx_dict(t['tx_hash'], formatted_amount=formatted_decimal(diff_closed))

                                        # if accept fully paid - close accept
                                        if part_bought >= 1.0:
                                            debug('... 100% paid accept '+sell_accept_tx['tx_hash']+'. closing accept for payments. remove alarm.')
                                            # remove alarm for accept
                                            remove_alarm(sell_accept_tx['tx_hash'])

                                        # if not more left in the offer (and it is not updated) - close sell
                                        sell_tx_updated=False
                                        try:
                                            if tx_dict[sell_offer_tx['tx_hash']][-1]['updated_by'] != None and tx_dict[sell_offer_tx['tx_hash']][-1]['updated_by'] != "unknown":
                                                sell_tx_updated=True
                                        except KeyError: # sell tx was not updated
                                            pass

                                        if not sell_tx_updated:
                                            if addr_dict[address][c]['offer'] == 0:
                                                debug('... sell offer closed for '+address)
                                                update_tx_dict(sell_offer_tx['tx_hash'], color='bgc-done', icon_text='Sell offer done')
                                                # remove alarm for accept
                                                debug('remove alarm for paid '+sell_accept_tx['tx_hash'])
                                                remove_alarm(sell_accept_tx['tx_hash'])
                                            else:
                                                debug('... sell offer is still open on '+address)
                                                update_tx_dict(sell_offer_tx['tx_hash'], color='bgc-accepted-done', icon_text='Sell offer partially done')
                                        else:
                                            debug('skip updating an updated sell offer on '+address)
                                            # remove alarm for accept
                                            debug('remove alarm for updated sell offer for paid '+sell_accept_tx['tx_hash'])
                                            remove_alarm(sell_accept_tx['tx_hash'])

                                        # heavy debug
                                        debug_address(address, c, 'after bitcoin payment')
                                        debug_address(from_address, c, 'after bitcoin payment')

                                        return True # hidden assumption: payment is for a single accept
                                    else:
                                        info('BUG: non positive part bought on bitcoin payment: '+t['tx_hash'])
                                else:
                                    debug('payment does not fit to accept: '+sell_accept_tx['tx_hash'])
    return False


# A fresh initialized address entry
def new_addr_entry():
    entry={}
    # for each currency
    for c in coins_list+['Bitcoin']:
        currency_dict={}
        # initialize all properties
        for property in addr_properties:
            if property.endswith('_tx'):
                 currency_dict[property]=[]
            else:
                 currency_dict[property]=0
        entry[c]=currency_dict
    entry['exodus']={'bought':0}
    return entry


# update the main tx database
# example call:
# update_tx_dict(tx_hash, icon='simplesend', color='bgc_done')
def update_tx_dict(tx_hash, *arguments, **keywords):
    # tx_hash is first arg
    # then come the keywords and values to be modified

    # is there already entry for this tx_hash?
    if not tx_dict.has_key(tx_hash):
        # no - so create a new one
        # remark: loading all tx for that tx_hash
        # for simplesend which is exodus, the last one is simplesend (#1)
        tx_dict[tx_hash]=load_dict_from_file('tx/'+tx_hash+'.json', all_list=True)

    # the last tx on the list is the one to modify
    n=-1

    # get the update_fs from tx_dict for that tx
    if tx_dict[tx_hash][n].has_key('update_fs'):
        update_fs=tx_dict[tx_hash][n]['update_fs']
    else:
        # start with default "no need to update fs"
        tx_dict[tx_hash][n]['update_fs']=False
        update_fs=False
    
    # update all given fields with new values
    keys = sorted(keywords.keys())
    # allow only keys from tx_properties
    for kw in keys:
        try:
            prop_index=tx_properties.index(kw)
        except ValueError:
            info('BUG: unsupported property of tx: '+kw)
            return False
        # set update_fs flag if necessary (if something really changed)
        try:
            update_fs = tx_dict[tx_hash][n][kw]!=keywords[kw] or update_fs
        except KeyError:
            update_fs = True
        tx_dict[tx_hash][n][kw]=keywords[kw]

    tx_dict[tx_hash][n]['update_fs']=update_fs
    return True


# debug dump of address values
def debug_address(addr,c, message="-"):
    if msc_globals.heavy_debug == True:
        debug('######## '+str(addr)+' '+str(c)+' '+str(message)+' >>>>>>>>')
        try:
            d=addr_dict[addr][c]
        except KeyError:
            debug('address does not exist in database')
            debug('>>>>>>>> '+str(addr)+' '+str(c)+' '+str(message)+' ########')
            return False
        debug('balance: '+str(d['balance']))
        debug('reserved: '+str(d['reserved']))
        debug('offer: '+str(d['offer']))
        debug('accept: '+str(d['accept']))
        debug('bought: '+str(d['bought']))
        debug('sold: '+str(d['sold']))
        debug('sent: '+str(d['sent']))
        debug('received: '+str(d['received']))
        debug('>>>>>>>> '+str(addr)+' '+str(c)+' '+str(message)+' ########')

# update the main address database
# example call:
# update_addr_dict('1address', True, 'Mastercoin', balance=10, bought=2, bought_tx=t)
# accomulate True means add on top of previous values
# accomulate False means replace previous values
def update_addr_dict(addr, accomulate, *arguments, **keywords):

    # update specific currency fields within address
    # address is first arg
    # accomulate is seccond arg
    # currency is third arg:
    # 'Mastercoin', 'Test Mastercoin', 'Bitcoin' or 'exodus' for exodus purchases
    # then come the keywords and values to be updated
    c=arguments[0]
    if c!='Mastercoin' and c!='Test Mastercoin' and c!='exodus' and c!= 'Bitcoin' and c!='Smart Property':
        info('BUG: update_addr_dict called with unsupported currency: '+c)
        return False
    
    # get the property name for smart property
    if c == 'Smart Property':
        c = arguments[1]

    # is there already entry for this address?
    if not addr_dict.has_key(addr):
        # no - so create a new one
        addr_dict[addr]=new_addr_entry()

    # smart property init for dict
    if c not in addr_dict[addr]:
        currency_dict={}
        # initialize all properties
        for property in addr_properties:
            if property.endswith('_tx'):
                 currency_dict[property]=[]
            else:
                 currency_dict[property]=0
        addr_dict[addr][c]=currency_dict

    # update all given fields with new values
    keys = sorted(keywords.keys())
    # allow only keys from addr_properties
    for kw in keys:
        try:
            prop_index=addr_properties.index(kw)
        except ValueError:
            info('unsupported property of addr: '+kw)
            return False

        if accomulate == True: # just add the tx or value
            if kw.endswith('_tx'):
                addr_dict[addr][c][kw].append(keywords[kw])
            else: # values are in satoshi
                addr_dict[addr][c][kw]+=int(keywords[kw])
                if addr_dict[addr][c][kw]<0:
                    # exodus address keeps only the expenses, and calculates dynamic balance on demand
                    if addr != exodus_address:
                        info('BUG: field '+kw+' on accomulated '+addr+' has '+str(addr_dict[addr][c][kw]))
                        return False
        else:
            if kw.endswith('_tx'): # replace the tx or value
                addr_dict[addr][c][kw]=[keywords[kw]]
            else: # values are in satoshi
                addr_dict[addr][c][kw]=int(keywords[kw])
                if addr_dict[addr][c][kw]<0:                
                    # exodus address keeps only the expenses, and calculates dynamic balance on demand
                    if addr != exodus_address:
                        info('BUG: field '+kw+' on '+addr+' has '+str(addr_dict[addr][c][kw]))
                        return False
    return True


def update_initial_icon_details(t):
    # update fields icon, details
    update_tx_dict(t['tx_hash'], color='bgc-new')
    try:
        if t['transactionType']=='0000':
            update_tx_dict(t['tx_hash'], icon='simplesend', details=t['to_address'])
        else:
            if t['transactionType']=='0014':
                update_tx_dict(t['tx_hash'], icon='selloffer', details=t['formatted_price_per_coin'])
            else:
                if t['transactionType']=='0016':
                    update_tx_dict(t['tx_hash'], icon='sellaccept', details='unknown_price')
                else:
                    update_tx_dict(t['tx_hash'], icon='unknown', details='unknown')
    except KeyError as e:
        # The only *valid* mastercoin tx without transactionType is exodus
        if t['tx_type_str']=='exodus':
            try:
                update_tx_dict(t['tx_hash'], icon='exodus', details=t['to_address'])
            except KeyError:
                info('BUG: exodus tx with no to_address: '+str(t))
                return False
        else:
            info('BUG: non exodus valid msc tx without '+str(e)+' ('+t['tx_type_str']+') on '+t['tx_hash'])
            return False
    return True

def mark_tx_invalid(tx_hash, reason):
    # mark tx as invalid
    update_tx_dict(tx_hash, invalid=(True,reason), color='bgc-invalid')

# add another sell tx to the modified dict
def add_offers(key, t):
    if offers_dict.has_key(key):
        offers_dict[key].append(t['tx_hash'])
    else:
        offers_dict[key]=[t['tx_hash']]

# add another property  to the modified dict
def add_properties(key, t):
    if properties_dict.has_key(key):
        properties_dict[key].append(t['tx_hash'])
    else:
        properties_dict[key]=[t['tx_hash']]

# write back to fs all tx which got modified
def write_back_modified_tx():
    n=-1 # relevant is last tx on the list
    for k in tx_dict.keys():
        if tx_dict[k][n]['update_fs'] == True:
            # remove update fs marker
            del tx_dict[k][n]['update_fs']
            # save back to filesystem
            atomic_json_dump(tx_dict[k], 'tx/'+k+'.json', add_brackets=False)

# create offers json
def update_offers():
    for tx_hash in offers_dict.keys():
        # generate tx list for each tx_hash
        offers=[]
        for b_hash in offers_dict[tx_hash]:
            offers.append(tx_dict[b_hash][-1])
        # write updated offers
        atomic_json_dump(offers, 'offers/offers-'+tx_hash+'.json', add_brackets=False)

# create prop json
def update_properties():
    for prop_id in properties_dict.keys():
        # generate tx list for each id
        properties=[]
        for prop_hash in properties_dict[prop_id]:
            properties.append(tx_dict[prop_hash][-1])
        # write updated props
        atomic_json_dump(properties, 'properties/properties-'+prop_id+'.json', add_brackets=False)

def update_bitcoin_balances():
    if msc_globals.b == True:
        # skip balance retrieval
        info('skip balance retrieval')
        return

    chunk=100
    addresses=addr_dict.keys()

    # cut into chunks
    for i in range(len(addresses)/chunk):
        addr_batch=addresses[i*chunk:(i+1)*chunk]

        # create the string of all addresses
        addr_batch_str=''
        for a in addr_batch:
            if a != "unknown":
                addr_batch_str=addr_batch_str+a+' '

        # get the balances
        balances=get_balance(addr_batch_str)

        # update addr_dict with bitcoin balance
        for b in balances:
            update_addr_dict(b['address'], False, 'Bitcoin', balance=b['paid'])

def award_premine_to_issuer(issuer_addr):
    active_fundraiser = fundraisers_dict[issuer_addr]
    fundraiser_metadata = fundraisers_metadata_dict[active_fundraiser['tx_hash']]

    fundraiser_metadata['total_tokens_created'] = 0
    #percent for issuer calculation
    percentage_issuer = (int(active_fundraiser['percentageForIssuer'])*0.01)
    c = coins_dict.keys()[coins_dict.values().index(str(active_fundraiser['currencyId']))]
    for transaction in fundraiser_metadata['funded_tx']:
        bonus_seconds = int(active_fundraiser['deadline']) - int(transaction['tx_time'][:-3])
        bonus_percentage =  float( bonus_seconds)/604800 * float(active_fundraiser['earlybirdBonus'])/100 + 1

        amount_transfer=to_satoshi(transaction['formatted_amount'])
        if int(active_fundraiser['property_type']) == 2:
            #for property_type 2 (divisible)
            tokens_created=((amount_transfer*10e-9)*int(active_fundraiser['numberOfProperties']))*bonus_percentage
            fundraiser_metadata['total_tokens_created']+=tokens_created
        else:
            #for property_type 1(indivisible) note int type for calculation
            tokens_created=int(amount_transfer*10e-9*int(active_fundraiser['numberOfProperties'])*bonus_percentage)
            fundraiser_metadata['total_tokens_created']+=tokens_created

    #add Z% of Y Tokens and assign to issuer
    total_tokens_premine=fundraiser_metadata['total_tokens_created']*percentage_issuer
    
    if int(active_fundraiser['property_type']) == 2:
        total_tokens_missed=total_tokens_premine-fundraiser_metadata['current_premine']
    else:
        total_tokens_missed=int(total_tokens_premine-fundraiser_metadata['current_premine'])

    info(["final total premined", total_tokens_premine, "tokens missed", total_tokens_missed, "metadata", fundraiser_metadata])
    update_addr_dict(issuer_addr, True,'Smart Property', c, balance=total_tokens_missed, received=total_tokens_missed, in_tx=active_fundraiser)

def check_active_fundraisers(time_block):
    import time
    for address in fundraisers_dict.keys():
        deadline = int(fundraisers_dict[address]['deadline'])
        if not (time_block < deadline): #fundraiser deadline has not been reached
            debug(['Deleted fundraiser', address])
            award_premine_to_issuer(address)
            del fundraisers_dict[address]
# generate api json
# address
# general files (10 in a page)
# mastercoin_verify
def generate_api_jsons():

    # prepare updated snapshot of bitcoin balances for all addresses
    update_bitcoin_balances()

    # create file for each address
    for addr in addr_dict.keys():
        balances_list=[]
        addr_dict_api={}
        addr_dict_api['address']=addr
        
        #takes keys including smart properties minus exodus and btc
        addr_keys = addr_dict[addr].keys()
        addr_keys.remove('exodus')
        addr_keys.remove('Bitcoin')

        for c in addr_keys:
            sub_dict={}
            sub_dict['received_transactions']=addr_dict[addr][c]['in_tx']
            sub_dict['received_transactions'].reverse()
            sub_dict['sent_transactions']=addr_dict[addr][c]['out_tx']
            sub_dict['sent_transactions'].reverse()
            sub_dict['bought_transactions']=addr_dict[addr][c]['bought_tx']
            sub_dict['bought_transactions'].reverse()
            sub_dict['sold_transactions']=addr_dict[addr][c]['sold_tx']
            sub_dict['sold_transactions'].reverse()
            sub_dict['offer_transactions']=addr_dict[addr][c]['offer_tx']
            sub_dict['offer_transactions'].reverse()
            sub_dict['accept_transactions']=addr_dict[addr][c]['accept_tx']
            sub_dict['accept_transactions'].reverse()
            sub_dict['total_received']=from_satoshi(addr_dict[addr][c]['received'])
            sub_dict['total_sent']=from_satoshi(addr_dict[addr][c]['sent'])
            sub_dict['total_sold']=from_satoshi(addr_dict[addr][c]['sold'])
            sub_dict['total_bought']=from_satoshi(addr_dict[addr][c]['bought'])
            sub_dict['total_sell_accept']=from_satoshi(addr_dict[addr][c]['accept'])
            sub_dict['total_sell_offer']=from_satoshi(addr_dict[addr][c]['offer'])
            if addr==exodus_address:
                available_reward=get_available_reward(last_height, c)
                sub_dict['balance']=from_satoshi(available_reward+addr_dict[addr][c]['balance'])
            else:
                #if c is in smart_property_dict and is divisible, otherwise just normal is fine
                try:
                    property_type = property_type_dict[c]
                    if property_type == '0002':
                        sub_dict['balance']=from_satoshi(addr_dict[addr][c]['balance'])
                    else:
                        sub_dict['balance']=addr_dict[addr][c]['balance']
                except KeyError:
                    #assume normal divisible property like MSC or TMSC
                    sub_dict['balance']=from_satoshi(addr_dict[addr][c]['balance'])

                #DEBUG
                #if len(property_type_dict) > 0:
                #    info(['property types', property_type_dict, c, sub_dict['balance'], sub_dict])

            sub_dict['total_reserved']=from_satoshi(addr_dict[addr][c]['reserved'])
            sub_dict['exodus_transactions']=addr_dict[addr][c]['exodus_tx']
            sub_dict['exodus_transactions'].reverse()
            sub_dict['total_exodus']=from_satoshi(addr_dict[addr]['exodus']['bought'])
            balances_list.append({"symbol":coins_short_name_dict[c],"value":sub_dict['balance']})
            addr_dict_api[coins_dict[c]]=sub_dict
        balances_list.append({"symbol":"BTC","value":from_satoshi(addr_dict[addr]['Bitcoin']['balance'])})
        addr_dict_api['balance']=balances_list
        atomic_json_dump(addr_dict_api, 'addr/'+addr+'.json', add_brackets=False)

    # create files for msc and files for test_msc
    for k in tx_dict.keys():
        # take all tx list for this txid
        for t in tx_dict[k]:
            if t['invalid'] != False:
                continue
            if t['tx_type_str']=='exodus':
                sorted_currency_tx_list['Mastercoin'].append(t)
                sorted_currency_tx_list['Test Mastercoin'].append(t)
            else:
                try:
                    if t['currencyId']==reverse_currency_type_dict['Mastercoin']:
                        sorted_currency_tx_list['Mastercoin'].append(t)
                    else:
                        if t['currencyId']==reverse_currency_type_dict['Test Mastercoin']:
                            sorted_currency_tx_list['Test Mastercoin'].append(t)
                except KeyError as e:
                    info("BUG: Transaction without currencyId: "+str(t))
    # and reverse sort
    for c in coins_list:
        sorted_currency_tx_list[c]=sorted(sorted_currency_tx_list[c], \
            key=lambda k: (-int(k['block']),-int(k['index'])))

    chunk=10
    # create the latest transactions pages
    pages={'Mastercoin':0, 'Test Mastercoin':0}
    for c in coins_list:
        for i in range(len(sorted_currency_tx_list[c])/chunk):
            atomic_json_dump(sorted_currency_tx_list[c][i*chunk:(i+1)*chunk], \
                'general/'+coins_short_name_dict[c]+'_'+'{0:04}'.format(i+1)+'.json', add_brackets=False)
            pages[c]+=1

    # create the latest sell and accept transactions page
    for c in coins_list:
        for t in sorted_currency_tx_list[c]:
            if t['tx_type_str']=='Sell offer':
                sorted_currency_sell_tx_list[c].append(t)
            if t['tx_type_str']=='Sell accept':
                sorted_currency_accept_tx_list[c].append(t)

    # sort sells according to price
    for c in coins_list:
        sorted_currency_sell_tx_list[c]=sorted(sorted_currency_sell_tx_list[c], \
            key=lambda k: float(k['formatted_price_per_coin']))
        # filter the closed sell offers
        try:
            filtered_tx_list[c] = [t for t in sorted_currency_sell_tx_list[c] \
                if t['icon_text'] != 'Sell offer done' and t['icon_text'] != 'Depracated sell offer' and \
                    t['icon_text'] != 'Cancel request' and t['icon_text'] != 'Sell offer cancelled']
        except KeyError:
            error('tx without icon_text '+t['tx_hash'])
        sorted_currency_sell_tx_list[c] = filtered_tx_list[c]

    sell_pages={'Mastercoin':0, 'Test Mastercoin':0}
    accept_pages={'Mastercoin':0, 'Test Mastercoin':0}
    for c in coins_list:
        for i in range(len(sorted_currency_sell_tx_list[c])/chunk+1):
            atomic_json_dump(sorted_currency_sell_tx_list[c][i*chunk:(i+1)*chunk], \
                'general/'+coins_short_name_dict[c]+'_sell_'+'{0:04}'.format(i+1)+'.json', add_brackets=False)
            sell_pages[c]+=1
        for i in range(len(sorted_currency_accept_tx_list[c])/chunk+1):
            atomic_json_dump(sorted_currency_accept_tx_list[c][i*chunk:(i+1)*chunk], \
                'general/'+coins_short_name_dict[c]+'_accept_'+'{0:04}'.format(i+1)+'.json', add_brackets=False)
            accept_pages[c]+=1

    # update values.json
    values_list=load_dict_from_file('www/values.json', all_list=True, skip_error=True)
    # on missing values.json, take an empty default
    if values_list=={}:
        values_list=[{"currency": "MSC", "name": "Mastercoin", "name2": "", "pages": 1, "trend": "down", "trend2": "rgb(13,157,51)"}, \
                     {"currency": "TMSC", "name": "Test MSC", "name2": "", "pages": 1, "trend": "up", "trend2": "rgb(212,48,48)"}]
    updated_values_list=[]
    for v in values_list:
        v['pages']=pages[coins_reverse_short_name_dict[v['currency']]]
        v['accept_pages']=accept_pages[coins_reverse_short_name_dict[v['currency']]]
        v['sell_pages']=sell_pages[coins_reverse_short_name_dict[v['currency']]]
        updated_values_list.append(v)
    atomic_json_dump(updated_values_list, 'www/values.json', add_brackets=False)

    # create /mastercoin_verify/addresses/$currency
    for c in coins_list:
        mastercoin_verify_list=[]
        subdir=coins_dict[c]
        for addr in addr_dict.keys():
            sub_dict={}
            sub_dict['address']=addr
            if addr==exodus_address:
                available_reward=get_available_reward(last_height, c)
                sub_dict['balance']=from_satoshi(available_reward+addr_dict[addr][c]['balance'])
            else:
                sub_dict['balance']=from_satoshi(addr_dict[addr][c]['balance'])
            mastercoin_verify_list.append(sub_dict)
        atomic_json_dump(sorted(mastercoin_verify_list, key=lambda k: k['address']), 'mastercoin_verify/addresses/'+subdir, add_brackets=False)

    # create /mastercoin_verify/transactions/<ADDRESS>
    for addr in addr_dict.keys():
        single_addr_tx_dict={}
        verify_tx_dict={}
        verify_tx_list=[]
        for c in coins_list:
            for t in addr_dict[addr][c]['exodus_tx']+addr_dict[addr][c]['in_tx']+addr_dict[addr][c]['out_tx']:
                if t['invalid']==False:
                    verify_tx_dict[t['tx_hash']]=True
                else:
                    verify_tx_dict[t['tx_hash']]=False
        # collect all unique entries
        for key, value in verify_tx_dict.iteritems():
            verify_tx_list.append({'tx_hash':key, 'valid':value})
        mastercoin_verify_tx_per_address={'address':addr, 'transactions':verify_tx_list}
        atomic_json_dump(mastercoin_verify_tx_per_address, 'mastercoin_verify/transactions/'+addr, add_brackets=False)     
        
def get_available_reward(height, c):
    available_reward=0
    if c == 'Mastercoin':
        all_reward=5631623576222
        (block_timestamp, err)=get_block_timestamp(height)
        if block_timestamp == None:
            error('failed getting block timestamp of '+str(height)+': '+err)
        seconds_passed=block_timestamp-exodus_bootstrap_deadline
        years=(seconds_passed+0.0)/seconds_in_one_year
        part_available=1-0.5**years
        available_reward=all_reward*part_available
    return round(available_reward)

# validate a matercoin transaction
def check_mastercoin_transaction(t, index=-1):

    debug('block '+t['block'])

    # update icon and details
    update_initial_icon_details(t)
    t=tx_dict[t['tx_hash']][index]

    # get general data from tx
    to_addr=t['to_address']
    from_addr=t['from_address']
    amount_transfer=to_satoshi(t['formatted_amount'])
    currency=t['currency_str']
    tx_hash=t['tx_hash']
    tx_age=int(last_height) - int(t['block'])+1
    try:
        is_exodus=t['exodus']
    except KeyError:
        is_exodus=False

    if is_exodus: # assume exodus does not do sell offer/accept
        # exodus purchase
        update_addr_dict(to_addr, True, 'Mastercoin', balance=amount_transfer, exodus_tx=t)
        update_addr_dict(to_addr, True, 'Test Mastercoin', balance=amount_transfer, exodus_tx=t)
        update_addr_dict(to_addr, True, 'exodus', bought=amount_transfer)
        # exodus bonus - 10% for exodus (available slowly during the years)
        ten_percent=int((amount_transfer+0.0)/10+0.5)
        update_addr_dict(exodus_address, True, 'Mastercoin', reward=ten_percent, exodus_tx=t)
        update_addr_dict(exodus_address, True, 'Test Mastercoin', reward=ten_percent, exodus_tx=t)

        # all exodus are done
        update_tx_dict(t['tx_hash'], color='bgc-done', icon_text='Exodus')
    else:
        c=currency
        if c!='Mastercoin' and c!='Test Mastercoin' and c!='Smart Property':
            debug('unknown currency '+currency+ ' in tx '+tx_hash)
            return False
        # left are normal transfer and sell offer/accept
        if t['tx_type_str']==transaction_type_dict['0000']:

            transaction_smartProperty=False
            # need to get actual currency name at this point
            if c == 'Smart Property':
                # print >> sys.stderr, 'Looking up smart property name'
                transaction_smartProperty=True
                try:
                    c = coins_dict.keys()[coins_dict.values().index(str(int(t['currencyId'],16)))]
                except ValueError:
                    debug('invalid currency identifier'+tx_hash)
                    mark_tx_invalid(tx_hash, 'pay with a non existing currency')
                    return False 
                # print >> sys.stderr, 'Smart property name: ' + c
                # print >> sys.stderr, '   currencyId: ' + str(int(t['currencyId'],16))
            # heavy debug
            debug_address(from_addr,c, 'before simplesend')
            debug_address(to_addr,c, 'before simplesend')

            #check active_raisers dict if to_addr has open fundraiser
            if to_addr in fundraisers_dict.keys() and int(fundraisers_dict[to_addr]['currencyIdentifierDesired'],16) == int(t['currencyId'],16):
                transaction_activeFundraiser=True
                info(['active fundraiser send detected',t])
            else:
                transaction_activeFundraiser=False

            if tx_age <= blocks_consider_new:
                update_tx_dict(t['tx_hash'], color='bgc-new', icon_text='Simple send ('+str(tx_age)+' confirms)')
            else:
                if tx_age < blocks_consider_mature:
                    update_tx_dict(t['tx_hash'], color='bgc-new-done', icon_text='Simple send ('+str(tx_age)+' confirms)')
                else:
                    update_tx_dict(t['tx_hash'], color='bgc-done', icon_text='Simple send')
 
            # the normal transfer case
            if not addr_dict.has_key(from_addr):
                debug('try to pay from non existing address at '+tx_hash)
                mark_tx_invalid(tx_hash, 'pay from a non existing address')
                return False 
            else:
                if from_addr==exodus_address:
                    # in the exodus case, the balance to spend is the available reward
                    # plus the negative balance
                    available_reward=get_available_reward(t['block'], c)
                    balance_from=available_reward+addr_dict[from_addr][c]['balance']
                else:
                    # print >> sys.stderr,  'Getting keys from address: ' + str( from_addr )
                    #for key in addr_dict[from_addr]:
                    #    print  >> sys.stderr, '   ' + str( key )

                    # print >> sys.stderr, 'Sending funds to: ' + str( to_addr )
                    if c in addr_dict[from_addr]:
                        balance_from=addr_dict[from_addr][c]['balance']
                    else:
                        debug( 'Property ' + c + ' does not exist on ' + from_addr + ' in ' + tx_hash )
                        mark_tx_invalid( tx_hash, 'nonexistent property on source address' )
                        return False

                if amount_transfer > int(balance_from):
                    debug('balance of '+currency+' is too low on '+tx_hash)
                    mark_tx_invalid(tx_hash, 'balance too low')
                    return False
                else:
                    if transaction_smartProperty == True:
                        # update to_addr
                        update_addr_dict(to_addr, True,'Smart Property', c, balance=amount_transfer, received=amount_transfer, in_tx=t)
                        # update from_addr
                        update_addr_dict(from_addr, True,'Smart Property', c, balance=-amount_transfer, sent=amount_transfer, out_tx=t)
                    else:
                        if transaction_activeFundraiser == True:
                            # update the balances for the main currency
                            update_addr_dict(to_addr, True, c, balance=amount_transfer, received=amount_transfer, in_tx=t)
                            update_addr_dict(from_addr, True, c, balance=-amount_transfer, sent=amount_transfer, out_tx=t)
                            
                            #update the balances for the smart property being funded
                            active_fundraiser = fundraisers_dict[to_addr]
                            fundraiser_hash = active_fundraiser['tx_hash']
                            #bonus calculation

                            bonus_seconds = int(active_fundraiser['deadline']) - int(t['tx_time'][:-3])
                            info(["bonus calc", float(bonus_seconds)/604800, float(active_fundraiser['earlybirdBonus'])/100, active_fundraiser['earlybirdBonus'] ])
                            bonus_percentage =  float(bonus_seconds)/604800 * (float(active_fundraiser['earlybirdBonus'])/100) + 1
                            #percent for issuer calculation
                            percentage_issuer = (int(active_fundraiser['percentageForIssuer'])*0.01)

                            c = coins_dict.keys()[coins_dict.values().index(str(active_fundraiser['currencyId']))]

                            if int(active_fundraiser['property_type']) == 2:
                                #for property_type 2 (divisible)
                                tokens_created=((amount_transfer*10e-9)*int(active_fundraiser['numberOfProperties']))*bonus_percentage
                                #add Z% of Y Tokens and assign to issuer
                                tokens_percent_issuer=tokens_created*percentage_issuer 

                                #add %bonus and assign to buyer here
                                update_addr_dict(from_addr, True,'Smart Property', c, balance=tokens_created, received=tokens_created, in_tx=active_fundraiser)
                                update_addr_dict(to_addr, True,'Smart Property', c, balance=tokens_percent_issuer, received=tokens_percent_issuer, in_tx=t)


                                info(["Bonus percentage", bonus_percentage, "percent for issuer", percentage_issuer,"total created", tokens_created, "tokens for issuer", tokens_percent_issuer])
                                fundraisers_metadata_dict[fundraiser_hash]['funded_tx'].append(t)
                                fundraisers_metadata_dict[fundraiser_hash]['current_premine']+= tokens_percent_issuer
                            else:
                                #for property_type 1(indivisible) note int type for calculation
                                tokens_created=int(amount_transfer*10e-9*int(active_fundraiser['numberOfProperties'])*bonus_percentage)
                                #add Z% of Y Tokens and assign to issuer
                                tokens_percent_issuer=tokens_created*percentage_issuer 
                                
                                #for property_type 1 (non-divisible) use ints for calculating the amount_transfer
                                update_addr_dict(from_addr, True,'Smart Property', c, balance=tokens_created, received=tokens_created, in_tx=active_fundraiser)
                                update_addr_dict(to_addr, True,'Smart Property', c, balance=tokens_percent_issuer, received=tokens_percent_issuer, in_tx=t)
                                fundraisers_metadata_dict[fundraiser_hash]['funded_tx'].append(t)
                                fundraisers_metadata_dict[fundraiser_hash]['current_premine']+= tokens_percent_issuer

                                info(["Bonus percentage", bonus_percentage, "percent for issuer", percentage_issuer,"total created", tokens_created, "tokens for issuer", tokens_percent_issuer])

                            update_tx_dict(t['tx_hash'], fundraiser_send=['true', active_fundraiser['currencyId']])
                        else:
                            update_addr_dict(to_addr, True, c, balance=amount_transfer, received=amount_transfer, in_tx=t)
                            # update from_addr
                            update_addr_dict(from_addr, True, c, balance=-amount_transfer, sent=amount_transfer, out_tx=t)

                    debug('simplesend '+str(amount_transfer)+' '+c+' from '+from_addr+' to '+to_addr+' '+tx_hash)

                    # heavy debug
                    debug_address(from_addr,c, 'after simplesend')
                    debug_address(to_addr,c, 'after simplesend')

                    return True
        else:

            # check history bugs (currently relevant for sell offer and accepts)
            #for tx_check in invalidate_tx_list:
            #    if t['tx_hash'] == tx_check:
            #        mark_tx_invalid(t['tx_hash'], 'avoid changing history')

            # sell offer
            if t['tx_type_str']==transaction_type_dict['0014']:
                debug('sell offer from '+t['from_address']+' '+t['tx_hash'])
                transaction_version=t['transactionVersion']
                if transaction_version != '0000' and transaction_version != '0001':
                    info('non supported sell offer with transaction version '+transaction_version)
                    mark_tx_invalid(t['tx_hash'], 'non supported sell offer with transaction version '+transaction_version)
                    return False

                # get reserved funds on address
                try:
                    seller_reserved=from_satoshi(addr_dict[from_addr][c]['reserved'])
                except KeyError: # no such address
                    seller_reserved=0.0
                satoshi_seller_reserved=to_satoshi(seller_reserved)

                # get previous offer on address
                try:
                    previous_seller_offer=from_satoshi(addr_dict[from_addr][c]['offer'])
                except KeyError: # no such address
                    previous_seller_offer=0.0

                # get user declared offer
                seller_offer=t['formatted_amount']

                # check which action
                # for backwards compatibility we accept transaction version 0
                if transaction_version == '0000':
                    # if offer is zero - it is action 3 (cancel)
                    if float(seller_offer) == 0:
                        action='03'
                    # otherwise, it is action 1 (new) or action 2 (update)
                    else:
                        if float(seller_reserved) != 0:
                            # that's an update
                            action='02'
                        else:
                            # a new transaction
                            action='01'
                    action_str=sell_offer_action_dict[action]
                    # update action and action_str on tx (so it behaves like transaction version 1)
                    debug('action_str of '+t['tx_hash']+' is modified to '+action_str)
                    update_tx_dict(t['tx_hash'], action=action, action_str=action_str)
                else:
                    action=t['action']

                bitcoin_amount_desired=float(t['formatted_bitcoin_amount_desired'])
                # allow bitcoin amount desired to be zero only on cancel action
                if bitcoin_amount_desired == 0 and action != '03':
                    info('zero bitcoin amount desired on '+t['tx_hash'])
                    mark_tx_invalid(t['tx_hash'], 'zero bitcoins amount desired')
                    return False

                # new/update/cancel
                if action == '01':
                        info('new sell offer on '+from_addr+' '+t['tx_hash'])
                else:
                    if action == '02':
                        # update allowed only if prior exists. mark old updated_by.
                        if float(seller_reserved) != 0:
                            info('update sell offer on '+from_addr)
                        else:
                            mark_tx_invalid(t['tx_hash'], 'invalid update offer since no prior offer exits')
                            info('invalid update sell offer: no prior offer exits on '+from_addr+' '+t['tx_hash'])
                            return False
                    else:
                        if action == '03':
                            # cancel allowed only if prior exists. mark cancelled (some funds sold).
                            if float(seller_reserved) != 0:
                                info('cancel sell offer on '+from_addr+' '+t['tx_hash'])
                            else:
                                mark_tx_invalid(t['tx_hash'], 'invalid cancel offer since no prior offer exits')
                                info('invalid cancel sell offer: no prior offer exits on '+from_addr+' '+t['tx_hash'])
                                return False
                        else:
                            info('non supported action on sell offer '+t['tx_hash'])
                            mark_tx_invalid(t['tx_hash'], 'invalid sell offer action '+action)
                            return False

                # get balance
                try:
                    seller_balance=from_satoshi(addr_dict[from_addr][c]['balance'])
                except KeyError: # no such address
                    seller_balance=0.0

                # heavy debug - before change
                debug_address(from_addr,c, 'before sell offer')

                # first handle a new offer
                if action == '01':
                    # assert on existing reserved
                    if float(seller_reserved) != 0:
                        info('invalid new sell offer version '+str(transaction_version)+ \
                            ' after prior sell offer with reserved '+str(seller_reserved)+ \
                            ' on '+from_addr+' '+t['tx_hash'])
                        mark_tx_invalid(t['tx_hash'], 'new sell offer version '+str(transaction_version)+' after prior sell offer')
                        return False

                    # calculate offer:
                    # limit offer with balance
                    actual_offer=min(float(seller_balance), float(seller_offer))

                    # no sell offers of zero (e.g. due to zero balance) are allowed
                    if actual_offer == 0:
                        mark_tx_invalid(t['tx_hash'], 'new zero sell offer (was '+str(seller_offer)+')')
                        info('invalid new zero sell offer sell offer was ('+str(seller_offer)+')')
                        return False

                    # update tx
                    debug('update amount available of '+formatted_decimal(actual_offer)+' on tx '+t['tx_hash'])
                    update_tx_dict(t['tx_hash'], icon_text='Sell Offer ('+str(tx_age)+' confirms)', \
                        amount_available=actual_offer, formatted_amount_available=formatted_decimal(actual_offer))
                    # update address with new offer balance and reserved
                    update_addr_dict(from_addr, True, c, offer=to_satoshi(actual_offer), reserved=to_satoshi(actual_offer), \
                        balance=-to_satoshi(actual_offer), offer_tx=t)
                else:
                    if action == '02':
                        # assert on non existing reserved
                        if float(seller_reserved) == 0:
                            info('BUG: a sell offer update of a zero reserved address on '+from_addr+' '+t['tx_hash'])
                            return False

                        # mark previous sell offer as updated + update next
                        previous_sell_offer=addr_dict[from_addr][c]['offer_tx'][-1]
                        # update updated_by on previous offer
                        update_tx_dict(previous_sell_offer['tx_hash'], updated_by=t['tx_hash'], \
                            icon_text='Depracated sell offer', color='bgc-expired')
                        # update updating on current offer
                        update_tx_dict(t['tx_hash'], updating=previous_sell_offer['tx_hash'], \
                            icon_text='Sell Offer ('+str(tx_age)+' confirms)', color='bgc-new')

                        # check how much already got accepted from this sell offer
                        already_accepted=float(seller_reserved)-float(previous_seller_offer)
                        satoshi_already_accepted=to_satoshi(already_accepted)

                        # update address - reserved (limitted by already_accepted) move back to balance:
                        update_addr_dict(from_addr, True, c, balance=satoshi_seller_reserved-satoshi_already_accepted, \
                            reserved=-satoshi_seller_reserved+satoshi_already_accepted)
                        # reset offer
                        update_addr_dict(from_addr, False, c, offer=0)

                        # get balance (after update)
                        try:
                            seller_balance=from_satoshi(addr_dict[from_addr][c]['balance'])
                        except KeyError: # no such address
                            seller_balance=0.0

                        # get reserved (after update, should be equal to standing accepts if any)
                        try:
                            seller_reserved=from_satoshi(addr_dict[from_addr][c]['reserved'])
                        except KeyError: # no such address
                            seller_reserved=0.0

                        if float(seller_reserved) != already_accepted:
                            debug('NOTICE: reserved does not equal to standing accepts during sell offer update '+t['tx_hash'])

                        # calculate offer:
                        # limit offer with balance (after the revert of old offer)
                        actual_offer=min(float(seller_balance), float(seller_offer))

                        debug('seller_balance is '+str(seller_balance)+' in '+t['tx_hash'])
                        debug('seller_reserved is '+str(seller_reserved)+' in '+t['tx_hash'])
                        debug('seller_offer is '+str(seller_offer)+' in '+t['tx_hash'])
                        debug('actual_offer updated to '+formatted_decimal(actual_offer)+' in '+t['tx_hash'])

                        # no sell offers of zero (e.g. due to zero balance) are allowed
                        if actual_offer == 0:
                            mark_tx_invalid(t['tx_hash'], 'update zero sell offer (was '+str(seller_offer)+')')
                            info('invalid updated zero sell offer sell offer was ('+str(seller_offer)+')')
                            return False

                        # update tx
                        debug('re-update amount available of '+formatted_decimal(actual_offer)+' on tx '+t['tx_hash'])
                        update_tx_dict(t['tx_hash'], icon_text='Updated sell Offer ('+str(tx_age)+' confirms)', \
                            amount_available=actual_offer, formatted_amount_available=formatted_decimal(actual_offer))
                        # update address with new offer balance and reserved
                        update_addr_dict(from_addr, True, c, offer=to_satoshi(actual_offer), reserved=to_satoshi(actual_offer), \
                            balance=-to_satoshi(actual_offer), offer_tx=t)

                    else:
                        if action == '03':
                            # assert on non existing reserved
                            if float(seller_reserved) == 0:
                                info('BUG: a sell offer cancel of a zero reserved address on '+from_addr+' '+t['tx_hash'])
                                return False

                            # mark previous sell offer as updated + current as cancelled
                            previous_sell_offer=addr_dict[from_addr][c]['offer_tx'][-1]
                            # update updated_by on previous offer
                            update_tx_dict(previous_sell_offer['tx_hash'], updated_by=t['tx_hash'], \
                                icon_text='Sell offer cancelled', color='bgc-expired')
                            # update updating on current offer
                            update_tx_dict(t['tx_hash'], updating=previous_sell_offer['tx_hash'], \
                                icon_text='Cancel request', color='bgc-expired')

                            # update address - reserved move back to balance:
                            # if there are running accepts - balance increases with offer (the rest will be added if accept expired)
                            # otherwise, balance increases with the whole reserved

                            accept_offers_running = False
                            # now find the relevant accept check if still running
                            try:
                                offers_hash_list=offers_dict[previous_sell_offer['tx_hash']]
                                debug(offers_hash_list)
                                for offer_hash in offers_hash_list: # go over all accepts
                                    # is accept exhausted?
                                    sell_accept_tx=tx_dict[offer_hash][-1]
                                    if sell_accept_tx['formatted_amount_accepted'] == sell_accept_tx['formatted_amount_bought']:
                                        debug('accept_offer_running exhausted...')
                                        debug('irrelevant fully paid accept '+sell_accept_tx['tx_hash'])
                                        continue
                                    else:
                                        debug('accept_offer_running NOT exhausted')
 
                                    # now check if block time limit expired
                                    block_time_limit=int(previous_sell_offer['formatted_block_time_limit'])
                                    sell_accept_block=int(sell_accept_tx['block'])
                                    current_block=int(t['block'])
                                    if sell_accept_block+block_time_limit >= current_block:
                                        debug('still running accept after cancel sell offer on '+sell_accept_tx['tx_hash'])
                                        accept_offers_running = True
                                        break
                                    else:
                                        debug('accept already expired')

                            except KeyError:
                                debug('no running accept for sell offer '+previous_sell_offer['tx_hash'])

                            if accept_offers_running:
                                debug('accept offer was running - add only offer to balance')
                                update_addr_dict(from_addr, True, c, balance=addr_dict[from_addr][c]['offer'], \
                                    reserved=-satoshi_seller_reserved, offer_tx=t)
                            else:
                                debug('NO accept offer was running - add all reserved to balance')
                                update_addr_dict(from_addr, True, c, balance=satoshi_seller_reserved, \
                                    reserved=-satoshi_seller_reserved, offer_tx=t)
                            # reset offer
                            update_addr_dict(from_addr, False, c, offer=0)

                # heavy debug - after change
                debug_address(from_addr,c, 'after sell offer')

                return True
            else:
                # sell accept
                if t['tx_type_str']==transaction_type_dict['0016']:
                    debug('sell accept from '+t['from_address']+' to '+t['to_address']+' '+t['tx_hash'])

                    # mark active only if sell offer is active

                    update_tx_dict(t['tx_hash'], icon_text='Sell Accept (active)')
                    # verify corresponding sell offer exists and partial balance
                    
                    try:
                        accept_amount_requested=t['formatted_amount_requested']
                    except KeyError:
                        accept_amount_requested=0.0
                    try:
                        sell_addr_entry = addr_dict[to_addr][c]
                    except (KeyError, IndexError):
                        # offer from wallet without entry (empty wallet)
                        info('accept offer from missing seller '+to_addr)
                        mark_tx_invalid(tx_hash, 'accept offer with missing sell offer')
                        return False

                    try:
                        sell_offer_tx=sell_addr_entry['offer_tx'][-1] # get orig offer tx (last) from seller
                    except (KeyError, IndexError):
                        # offer from wallet without entry (empty wallet)
                        info('accept offer from missing offer tx on seller '+to_addr)
                        mark_tx_invalid(tx_hash, 'accept offer with missing seller tx on sell offer')
                        return False

                    debug('match sell accept '+t['tx_hash']+' with sell offer '+sell_offer_tx['tx_hash'])

                    try:
                        amount_available=float(sell_offer_tx['amount_available']) # get orig offer from seller
                    except (KeyError, IndexError):
                        # offer from wallet without entry (empty wallet)
                        info('accept offer from missing amount available on seller '+to_addr)
                        mark_tx_invalid(tx_hash, 'accept offer with missing amount available on sell offer')
                        return False
                 
                    # invalidate accept of closed offers
                    debug('with sell offer amount available of '+str(amount_available))
                    if float(amount_available) == 0:
                        info('accept offer for closed sell offer on '+to_addr)
                        mark_tx_invalid(tx_hash, 'accept offer for closed sell offer')
                        return False

                    # invalidate accept for addresses that already have a running accept from that address
                    try:
                        offers_hash_list=offers_dict[sell_offer_tx['tx_hash']]
                        for b_hash in offers_hash_list:
                            b = tx_dict[b_hash][-1]
                            try:
                                payment_expired=b['payment_expired']
                            except KeyError:
                                payment_expired=False
                            try:
                                payment_done=b['payment_done']
                            except KeyError:
                                payment_expired=False

                            if not (payment_expired or payment_done) and b['from_address']==t['from_address']:
                                info('invalidate accept since a running accept for sell offer from that address exists '+t['tx_hash'])
                                mark_tx_invalid(tx_hash, 'sell offer has already a running accept from that address')
                                return False
                        debug('no accept offers from '+t['from_address']+' on sell offer yet')
                    except KeyError:
                        debug('no accept offers on sell offer yet')

                    # amount accepted is min between requested and offer
                    amount_accepted=min(float(accept_amount_requested),float(amount_available))

                    debug('amount accepted for '+t['tx_hash']+' is '+ str(amount_accepted))

                    # required fee calculation
                    try:
                        required_fee=float(sell_offer_tx['formatted_fee_required'])
                    except KeyError:
                        required_fee=0.0
                    try:
                        accept_fee=float(t['formatted_fee'])
                    except KeyError:
                        accept_fee=0.0

                    debug('required_fee is '+str(required_fee))
                    debug('accept_fee is '+str(accept_fee))

                    if float(accept_fee)<float(required_fee):
                        info('accept offer without minimal fee on tx: '+tx_hash)
                        mark_tx_invalid(tx_hash, 'accept offer without required fee')
                        return False
                    else:
                        debug('minimal fee is met')
                    
                    try:
                        # need to pay the part of the sell offer which got accepted
                        part=float(amount_accepted/float(sell_offer_tx['formatted_amount']))
                        bitcoin_required=float(sell_offer_tx['formatted_bitcoin_amount_desired'])*part
                    except KeyError:
                        bitcoin_required='missing required btc'

                    updated_amount_available = float(amount_available) - float(amount_accepted)

                    debug('update sell accept '+t['tx_hash']+' for address '+to_addr+' with amount accepted '+str(amount_accepted))
                    update_tx_dict(t['tx_hash'], bitcoin_required=formatted_decimal(bitcoin_required), \
                        sell_offer_txid=sell_offer_tx['tx_hash'], \
                        formatted_price_per_coin=sell_offer_tx['formatted_price_per_coin'], \
                        formatted_amount_accepted=str(amount_accepted), \
                        formatted_amount_bought='0.0', btc_offer_txid='unknown')

                    # heavy debug
                    debug_address(from_addr,c, 'before sell accept')
                    debug_address(to_addr,c, 'before sell accept')

                    if amount_accepted > 0: # ignore 0 or negative accepts
                        # update sell accept
                        update_tx_dict(t['tx_hash'], formatted_amount_accepted=amount_accepted, payment_done=False, payment_expired=False)
                        debug('add alarm for accept '+str(t))
                        add_alarm(t['tx_hash'])

                        # update sell offer
                        # update sell available: min between the remaining offer, and the current balance
                        debug('update sell offer '+sell_offer_tx['tx_hash']+' with amount available '+str(updated_amount_available))
                        update_tx_dict(sell_offer_tx['tx_hash'], amount_available=updated_amount_available, \
                            formatted_amount_available=formatted_decimal(updated_amount_available))

                        # update the amount offered on the seller side
                        debug('update sell address '+to_addr+' with reduced offer of '+str(amount_accepted))
                        update_addr_dict(to_addr, True, c, offer=-to_satoshi(amount_accepted))
                        debug('offer of '+to_addr+' is '+str(addr_dict[to_addr][c]['offer']))

                        # accomulate the amount accepted on the buyer side
                        update_addr_dict(from_addr, True, c, accept=to_satoshi(amount_accepted), accept_tx=t)

                        # update icon colors of sell
                        if amount_available > amount_accepted:
                            update_tx_dict(sell_offer_tx['tx_hash'], color='bgc-new-accepted', icon_text='Sell offer partially accepted')
                        else:
                            update_tx_dict(sell_offer_tx['tx_hash'], color='bgc-accepted', icon_text='Sell offer accepted')
                    else:
                        mark_tx_invalid(t['tx_hash'],'non positive amount accepted')

                    # add to current offers (which appear on seller tx)
                    key=sell_offer_tx['tx_hash']
                    add_offers(key, t)

                    # heavy debug
                    debug_address(from_addr,c, 'after sell accept')
                    debug_address(to_addr,c, 'after sell accept')
                    return True
                else:
                    if t['tx_type_str']==transaction_type_dict['0032'] or t['tx_type_str']==transaction_type_dict['0033']:
                        transaction_type=t['tx_type_str']
                        transaction_version=t['transactionVersion']
                        if transaction_version != '0000' and transaction_version != '0001':
                            info('non supported property version with transaction version '+transaction_version)
                            mark_tx_invalid(t['tx_hash'], 'non supported sell offer with transaction version '+transaction_version)
                            return False

                        debug('property creation from '+t['from_address']+' '+t['tx_hash'])

                        ecosystem = int(t['ecosystem'])
                        if ecosystem == 1 and int(t['block']) >= 297110:
			    count=0
			    for each in properties_dict.keys():
				if int(each) > 2 and int(each) < 2147483647:
				    count+=1	
                            prop_id=str(count + 3)  # +3 to not collide with MSC/TMSC
			elif ecosystem == 2:
			    count=0
			    for each in properties_dict.keys():
				if int(each) > 2147483650:
				    count+=1	
                            #determine prop_id
                            prop_id=str(count + 2147483651)  # +3 to not collide with MSC/TMSC
                        else:
                            mark_tx_invalid(tx_hash, 'TMSC/MSC are valid ecosystems only or MSC ecosystem before non-live block')
                            return False

                        if transaction_type == transaction_type_dict['0033']:
                            fundraiser = True
                        else:
                            fundraiser = False

                        if fundraiser: #active and valid fundraiser checks
                            if fundraisers_dict.has_key(from_addr):
                                mark_tx_invalid(t['tx_hash'],'already open fundraiser on this address at the current block')
                                return False

                            curr_desired = t['currencyIdentifierDesired']
                            try:
                                if int(curr_desired) > 3:
                                    valid_curr_desired=coins_dict.keys()[coins_dict.values().index(curr_desired)]
                            except ValueError:
                                debug('invalid currency identifier desired'+tx_hash)
                                mark_tx_invalid(tx_hash, 'desire non existing currency for fundraiser')
                                return False 

                        #used later in validation
                        property_type = t['property_type']
                        prev_prop_id = int(t['previous_property_id'])
                        #prop_cat = t['propertyCategory']
                        #prop_subcat = t['propertySubcategory']
                        prop_name = t['propertyName']
                        #prop_url = t['propertyUrl']
                        #prop_data = t['propertyData']

                        num_prop = t['numberOfProperties']
                        #deadline = t['deadline']
                        #earlybird_bonus = t['earlybirdBonus']
                        #percentage_for_issuer = t['percentageForIssuer']
                        
                        # add symbol to dict
                        property_type_dict[prop_name]=property_type
                        coins_dict[prop_name]=str(prop_id)
                        coins_short_name_dict[prop_name]='SP' + str(prop_id)
                        
                        # update property dict
                        t['currencyId'] = prop_id
                        add_properties(prop_id,t)

                        # update to_addr
                        if not fundraiser:
                            update_addr_dict(from_addr, True, c, prop_name, balance=num_prop, in_tx=t)
                        

                        if fundraiser: #active and valid fundraiser
                            info(['new fundraiser detected', from_addr, t])
                            fundraisers_dict[from_addr] = t
                            fundraisers_metadata_dict[t['tx_hash']] = {  'funded_tx': [], 'current_premine': 0}

                        return True
                    else:
                        if t['tx_type_str']==transaction_type_dict['0035']:
                            transaction_type=t['tx_type_str']
                            transaction_version=t['transactionVersion']
                            if transaction_version != '0000' and transaction_version != '0001':
                                info('non supported property version with transaction version '+transaction_version)
                                mark_tx_invalid(t['tx_hash'], 'non supported sell offer with transaction version '+transaction_version)
                                return False

                            if fundraisers_dict.has_key(from_addr) and (fundraisers_dict[from_addr]['currencyId'] == str(int(t['property_type'],16))):
                                info(['fundraiser cancellation detected, deleting: ', from_addr, t['tx_hash'] ])
                                award_premine_to_issuer(from_addr)
                                del fundraisers_dict[from_addr]
                                return True
                            else:
                                mark_tx_invalid(t['tx_hash'],'no open fundraisers on this address at the current block')
                                return False
                        else:
                            info('unknown tx type: '+t['tx_type_str']+' in '+tx_hash)
                            return False


#########################################################################
# main function - validates all tx and calculates balances of addresses #
#########################################################################
def validate():

    # parse command line arguments
    parser = OptionParser("usage: %prog [options]")
    parser.add_option("-d", "--debug", action="store_true",dest='debug_mode', default=False,
                        help="turn debug mode on")
    parser.add_option("-b", "--skip-balance", action="store_true",dest='skip_balance', default=False,
                        help="skip balance retrieval")

    (options, args) = parser.parse_args()
    msc_globals.init()
    msc_globals.d=options.debug_mode
    msc_globals.b=options.skip_balance

    # for heavy debugging
    msc_globals.heavy_debug = True

    # don't bother validating if no new block was generated
    last_validated_block=0
    try:
        f=open(LAST_VALIDATED_BLOCK_NUMBER_FILE,'r')
        last_validated_block=int(f.readline())
        f.close()
        if last_validated_block == int(last_height):
            info('last validated block '+str(last_validated_block)+' is identical to current height')
            exit(0)
    except IOError:
        pass

    info('starting validation process')

    # load tx_dict
    initial_tx_dict_load()

    # get all tx sorted
    sorted_tx_list=get_sorted_tx_list()

    # keep the last block which will get validated
    updated_last_validated_block=sorted_tx_list[-1]['block']

    # use an artificial empty last tx with last height as a trigger for alarm check
    sorted_tx_list.append({'invalid':(True,'fake tx'), 'block':last_height, 'tx_hash':'fake'})

    last_block=0 # keep tracking of last block for alarm purposes

    # go over all tx
    for t in sorted_tx_list:
        # check alarm (verify accept offers get payment in time)
        try:
            current_block=int(t['block'])
        except ValueError,e:
            error('invalid block number during validation: '+t['block'])
        check_alarm(t, last_block, current_block)
        
        if current_block > 292636 and t['tx_hash'] != 'fake': #first SP transaction
            current_timestamp=int(t['tx_time'][:-3])
            check_active_fundraisers(current_timestamp)
        # update last_block for next alarm check
        last_block=current_block

        try:
            if t['invalid'] == False: # normal valid mastercoin tx
                try:
                    if t['exodus']==True:
                        index=0 # for exodus take the first tx on the list
                except KeyError:
                    index=-1 # otherwise take the last tx in the list
                check_mastercoin_transaction(t, index)
            else: # maybe bitcoin payment
                if check_bitcoin_payment(t):
                    continue
                else: # report reason for invalid tx
                   debug(str(t['invalid'])+' '+t['tx_hash'])

        except OSError:
            error('error on tx '+t['tx_hash'])

    info('updating.. offers')
    # create json for offers
    update_offers()

    info('updating.. properties')
    # create json for properties
    update_properties()

    info('updating.. transactions')
    # update changed tx
    write_back_modified_tx()

    info('updating.. jsons')
    # generate address pages and last tx pages
    generate_api_jsons()

    info('done...')
    # write last validated block
    f=open(LAST_VALIDATED_BLOCK_NUMBER_FILE,'w')
    f.write(str(last_block)+'\n')
    f.close()

    info('validation done')

if __name__ == "__main__":
    validate()
