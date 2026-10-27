"""Django email backend that sends through Office 365 with Microsoft Graph (OAuth 2.0, no passwords).

The app signs in as itself with the client-credentials flow (tenant ID + client ID + client secret from
an Azure app registration) and calls /users/{mailbox}/sendMail. Microsoft is retiring basic-auth SMTP
for Exchange Online, so this avoids SMTP altogether. See AZURE.md, "Email (Office 365)".
"""
import base64
import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from email.utils import parseaddr

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

GRAPH_URL = 'https://graph.microsoft.com/v1.0'
TOKEN_URL = 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token'

# One token per process, shared by every send until shortly before it expires (tokens last ~1 hour).
_token = {'value': '', 'expires': 0.0}
_token_lock = threading.Lock()


def _post(url, body, headers, timeout):
    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode('utf-8', 'replace')[:1000]
        raise RuntimeError(f'Microsoft returned HTTP {e.code}: {detail}') from None


def _recipients(addresses):
    out = []
    for addr in addresses:
        name, email = parseaddr(addr)
        entry = {'address': email or addr}
        if name:
            entry['name'] = name
        out.append({'emailAddress': entry})
    return out


class GraphEmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.tenant_id = settings.MS_GRAPH_TENANT_ID
        self.client_id = settings.MS_GRAPH_CLIENT_ID
        self.client_secret = settings.MS_GRAPH_CLIENT_SECRET
        self.sender = settings.MS_GRAPH_SENDER or parseaddr(settings.DEFAULT_FROM_EMAIL)[1]
        self.save_to_sent = settings.MS_GRAPH_SAVE_TO_SENT
        self.timeout = settings.EMAIL_TIMEOUT or 30
        if not (self.tenant_id and self.client_id and self.client_secret and self.sender):
            raise ImproperlyConfigured('Office 365 email needs MS_GRAPH_TENANT_ID, MS_GRAPH_CLIENT_ID, '
                                       'MS_GRAPH_CLIENT_SECRET and MS_GRAPH_SENDER (or DEFAULT_FROM_EMAIL).')

    def _access_token(self):
        with _token_lock:
            if _token['value'] and _token['expires'] > time.time() + 60:
                return _token['value']
            body = urllib.parse.urlencode({
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'scope': 'https://graph.microsoft.com/.default',
            }).encode()
            data = json.loads(_post(TOKEN_URL.format(tenant=self.tenant_id), body,
                                    {'Content-Type': 'application/x-www-form-urlencoded'}, self.timeout))
            _token['value'] = data['access_token']
            _token['expires'] = time.time() + int(data.get('expires_in', 3600))
            return _token['value']

    def _payload(self, message):
        body, content_type = message.body, getattr(message, 'content_subtype', 'plain')
        # EmailMultiAlternatives: Graph takes one body, so prefer the HTML version when there is one.
        for content, mimetype in getattr(message, 'alternatives', None) or []:
            if mimetype == 'text/html':
                body, content_type = content, 'html'
                break

        msg = {
            'subject': message.subject,
            'body': {'contentType': 'HTML' if content_type == 'html' else 'Text', 'content': body},
            'toRecipients': _recipients(message.to),
            'ccRecipients': _recipients(message.cc),
            'bccRecipients': _recipients(message.bcc),
        }
        if message.reply_to:
            msg['replyTo'] = _recipients(message.reply_to)
        # A From other than the sending mailbox only works if that mailbox has "Send As" rights for it.
        from_email = parseaddr(message.from_email or '')[1]
        if from_email and from_email.lower() != self.sender.lower():
            msg['from'] = {'emailAddress': {'address': from_email}}

        attachments = []
        for att in message.attachments:
            if isinstance(att, tuple):  # (filename, content, mimetype)
                filename, content, mimetype = att
            else:  # a MIMEBase part
                filename = att.get_filename() or 'attachment'
                content, mimetype = att.get_payload(decode=True), att.get_content_type()
            if isinstance(content, str):
                content = content.encode('utf-8')
            attachments.append({
                '@odata.type': '#microsoft.graph.fileAttachment',
                'name': filename,
                'contentType': mimetype or 'application/octet-stream',
                'contentBytes': base64.b64encode(content).decode('ascii'),
            })
        if attachments:
            msg['attachments'] = attachments
        return {'message': msg, 'saveToSentItems': self.save_to_sent}

    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            if not message.recipients():
                continue
            try:
                url = f'{GRAPH_URL}/users/{urllib.parse.quote(self.sender)}/sendMail'
                _post(url, json.dumps(self._payload(message)).encode('utf-8'),
                      {'Authorization': f'Bearer {self._access_token()}',
                       'Content-Type': 'application/json'}, self.timeout)
                sent += 1
            except Exception:
                logger.exception('Office 365 email to %s failed', ', '.join(message.recipients()))
                if not self.fail_silently:
                    raise
        return sent
