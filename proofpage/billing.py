"""Hosted subscriptions. Only verified, freshly reconciled Stripe state grants access."""
import os
import secrets
import string
import threading
import time

BILLING_LOCK = threading.RLock()
API_VERSION = '2026-08-26.dahlia'

def plain(value):
    return value if isinstance(value, dict) else value.to_dict()


class Billing:
    def __init__(self, accounts, origin, client=None):
        self.accounts, self.origin = accounts, origin
        self.price_id = os.environ.get('PROOFPAGE_STRIPE_PRICE_ID','')
        self.webhook_secret = os.environ.get('PROOFPAGE_STRIPE_WEBHOOK_SECRET','')
        with accounts.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS checkouts(user_id TEXT PRIMARY KEY,session_id TEXT,request_key TEXT)')
        self.live = os.environ.get('PROOFPAGE_STRIPE_LIVE','false') == 'true'
        self.client = client
        key = os.environ.get('PROOFPAGE_STRIPE_KEY','')
        if key and self.client is None:
            from stripe import StripeClient
            self.client = StripeClient(key, stripe_version=API_VERSION, max_network_retries=2)

    @property
    def configured(self):
        return bool(self.client and self.price_id and self.webhook_secret)

    def price(self):
        if not self.configured:
            return {'configured':False,'detail':'Subscriptions are not configured on this server.'}
        p = plain(self.client.v1.prices.retrieve(self.price_id))
        if not p.get('active') or p.get('type') != 'recurring' or p.get('livemode') != self.live or p.get('unit_amount') is None:
            raise ValueError('Configure an active recurring flat price in the matching Stripe environment.')
        return {'configured':True,'amount':p['unit_amount'],'currency':p['currency'],'interval':p['recurring']['interval'],
                'interval_count':p['recurring']['interval_count'],'live':self.live}

    def checkout(self, user_id):
        self.price()
        if not self.configured:
            raise ValueError('Billing is not configured.')
        with BILLING_LOCK:
            user = self.accounts.user(user_id)
            if not user['customer']:
                customer = self.client.v1.customers.create({'email':user['email'],'metadata':{'proofpage_user':user_id}}, options={'idempotency_key':'proofpage-customer-'+user_id})
                with self.accounts.db() as db:
                    db.execute('UPDATE users SET customer=? WHERE id=?',(customer['id'],user_id))
                user = self.accounts.user(user_id)
            # Query authoritative state before opening another subscription checkout.
            existing = plain(self.client.v1.subscriptions.list({'customer':user['customer'],'status':'all','limit':100}))
            if any(s['status'] in ('active','trialing','past_due','unpaid','incomplete','paused') for s in existing['data']):
                raise ValueError('An existing subscription needs attention. Use Manage subscription.')
            with self.accounts.db() as db:
                saved = db.execute('SELECT * FROM checkouts WHERE user_id=?',(user_id,)).fetchone()
            if saved and saved['session_id']:
                prior = self.client.v1.checkout.sessions.retrieve(saved['session_id'])
                if prior['status'] == 'open':
                    return {'url':prior['url']}
                saved = None
            request_key = saved['request_key'] if saved else 'proofpage-checkout-'+secrets.token_hex(16)
            with self.accounts.db() as db:
                db.execute('INSERT OR REPLACE INTO checkouts VALUES(?,NULL,?)',(user_id,request_key))
            session = self.client.v1.checkout.sessions.create({
                'mode':'subscription','customer':user['customer'],'line_items':[{'price':self.price_id,'quantity':1}],
                'success_url':self.origin+'/?billing=returned','cancel_url':self.origin+'/?billing=cancelled',
                'client_reference_id':user_id,'subscription_data':{'metadata':{'proofpage_user':user_id}},
                'integration_identifier':'proofpage_qkzmhvta',
            }, options={'idempotency_key':request_key})
            with self.accounts.db() as db:
                db.execute('UPDATE checkouts SET session_id=? WHERE user_id=?',(session['id'],user_id))
        return {'url':session['url']}

    def portal(self, user_id):
        user = self.accounts.user(user_id)
        if not self.configured or not user['customer']:
            raise ValueError('No billing account is available.')
        session = self.client.v1.billing_portal.sessions.create({'customer':user['customer'],'return_url':self.origin+'/'})
        return {'url':session['url']}

    def reconcile(self, user_id):
        if not self.configured:
            raise ValueError('Billing is not configured.')
        with BILLING_LOCK:
            user = self.accounts.user(user_id)
            if not user['customer']:
                return self.accounts.account(user_id)
            subscriptions = plain(self.client.v1.subscriptions.list({'customer':user['customer'],'status':'all','limit':100}))
            if subscriptions.get('has_more'):
                raise ValueError('Billing account requires operator reconciliation.')
            eligible, latest = [], None
            for s in subscriptions['data']:
                if s.get('livemode') != self.live or s['customer'] != user['customer']:
                    continue
                items = s.get('items',{}).get('data',[])
                matching = [i for i in items if i['price']['id']==self.price_id and i.get('quantity',1)==1]
                if not matching:
                    continue
                latest = s if latest is None or s.get('created',0)>latest.get('created',0) else latest
                until = max((i.get('current_period_end',s.get('current_period_end',0)) for i in matching),default=0)
                if s['status'] in ('active','trialing') and until > time.time():
                    eligible.append((until,s))
            if eligible:
                until, subscription = max(eligible,key=lambda pair:pair[0])
                status, sid = subscription['status'], subscription['id']
            else:
                until, status, sid = 0, latest['status'] if latest else 'none', latest['id'] if latest else None
            with self.accounts.db() as db:
                db.execute('UPDATE users SET subscription=?,paid_until=?,billing_status=? WHERE id=?',(sid,until,status,user_id))
            self.accounts.audit(user_id,'billing.reconciled')
        return self.accounts.account(user_id)

    def webhook(self, body, signature):
        if not self.configured:
            raise ValueError('Billing is not configured.')
        import stripe
        try:
            event = plain(stripe.Webhook.construct_event(body,signature,self.webhook_secret,tolerance=300))
        except (ValueError,stripe.SignatureVerificationError):
            raise ValueError('Invalid webhook signature.') from None
        if event.get('livemode') != self.live:
            raise ValueError('Webhook environment mismatch.')
        supported = {'checkout.session.completed','checkout.session.async_payment_succeeded','customer.subscription.created',
                     'customer.subscription.updated','customer.subscription.deleted','invoice.paid','invoice.payment_failed'}
        with BILLING_LOCK:
            with self.accounts.db() as db:
                if db.execute('SELECT 1 FROM events WHERE id=?',(event['id'],)).fetchone():
                    return {'received':True,'duplicate':True}
            if event['type'] in supported:
                customer = event['data']['object'].get('customer')
                with self.accounts.db() as db:
                    user = db.execute('SELECT id FROM users WHERE customer=?',(customer,)).fetchone()
                if user:
                    # Never trust the event's entitlement, user metadata, ordering or success redirect.
                    self.reconcile(user['id'])
            with self.accounts.db() as db:
                db.execute('INSERT OR IGNORE INTO events VALUES(?,?)',(event['id'],time.time()))
        return {'received':True}
