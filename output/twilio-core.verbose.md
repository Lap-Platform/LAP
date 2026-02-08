# Twilio REST API API Documentation

Base URL: https://api.twilio.com/2010-04-01

Version: 2010-04-01

## Authentication

Bearer basic

## POST /Accounts/{AccountSid}/Messages.json

Send an SMS or MMS message

### Required Parameters

- **AccountSid** (str):  - The SID of the Account creating the Message resource
- **To** (str):  - The recipient phone number in E.164 format
- **Body** (str):  - The text content of the message (max 1600 characters)

### Optional Parameters

- **From** (str):  - A Twilio phone number in E.164 format, an alphanumeric sender ID, or a Channel Address
- **MessagingServiceSid** (str):  - The SID of the Messaging Service you want to associate with the Message
- **MediaUrl** ([str]):  - URL of media to include in the message. Up to 10 MediaUrl values.
- **StatusCallback** (str):  - The URL Twilio will POST to each time your message status changes
- **MaxPrice** (num):  - The maximum price in US dollars acceptable for the message
- **ValidityPeriod** (int):  - The number of seconds the message can remain in queue (1-14400)
- **SendAt** (str(date-time)):  - The time Twilio will send the message (ISO 8601 format, for scheduled messages)
- **ContentSid** (str):  - The SID of the content template for the message

## GET /Accounts/{AccountSid}/Messages.json

List messages

### Required Parameters

- **AccountSid** (str):  - The SID of the Account

### Optional Parameters

- **To** (str):  - Filter by recipient phone number
- **From** (str):  - Filter by sender phone number
- **DateSent** (str(date)):  - Filter by date sent (YYYY-MM-DD)
- **PageSize** (int):  - Number of records to return per page (max 1000)

## GET /Accounts/{AccountSid}/Messages/{MessageSid}.json

Fetch a message

### Required Parameters

- **AccountSid** (str):  - The SID of the Account
- **MessageSid** (str):  - The SID of the Message resource to fetch

## DELETE /Accounts/{AccountSid}/Messages/{MessageSid}.json

Delete a message

### Required Parameters

- **AccountSid** (str):  - The SID of the Account
- **MessageSid** (str):  - The SID of the Message resource to delete

## POST /Accounts/{AccountSid}/Calls.json

Make a phone call

### Required Parameters

- **AccountSid** (str):  - The SID of the Account creating the Call
- **To** (str):  - The phone number, SIP address, or Client identifier to call
- **From** (str):  - The phone number or Client identifier to use as the caller ID

### Optional Parameters

- **Url** (str):  - The URL that returns TwiML instructions for the call
- **Twiml** (str):  - TwiML instructions for the call (alternative to Url)
- **ApplicationSid** (str):  - The SID of the Application resource to handle the call
- **Method** (str):  - The HTTP method Twilio should use to request the Url
- **StatusCallback** (str):  - The URL Twilio will send call state change webhooks to
- **StatusCallbackMethod** (str):  - HTTP method for StatusCallback requests
- **Timeout** (int):  - Number of seconds Twilio will wait for the call to be answered (5-600)
- **Record** (bool):  - Whether to record the call
- **MachineDetection** (str):  - Enable answering machine detection
- **CallerId** (str):  - The phone number to display as the caller ID (for verified numbers)

## GET /Accounts/{AccountSid}/Calls.json

List calls

### Required Parameters

- **AccountSid** (str):  - The SID of the Account

### Optional Parameters

- **To** (str):  - Filter by recipient
- **From** (str):  - Filter by caller
- **Status** (str):  - Filter by call status
- **StartTime** (str(date)):  - Filter by start time (YYYY-MM-DD)
- **PageSize** (int):  - Number of records per page (max 1000)

## GET /Accounts/{AccountSid}/Calls/{CallSid}.json

Fetch a call

### Required Parameters

- **AccountSid** (str):  - The SID of the Account
- **CallSid** (str):  - The SID of the Call resource to fetch

## POST /Accounts/{AccountSid}/Calls/{CallSid}.json

Update a call

### Required Parameters

- **AccountSid** (str):  - The SID of the Account
- **CallSid** (str):  - The SID of the Call to update

### Optional Parameters

- **Url** (str):  - The URL for new TwiML instructions
- **Method** (str):  - HTTP method for the Url request
- **Status** (str):  - Set to canceled or completed to end the call
- **Twiml** (str):  - TwiML instructions for modifying the call
- **StatusCallback** (str):  - URL for call status webhooks
