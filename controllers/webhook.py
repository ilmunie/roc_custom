from odoo import http
from odoo.http import request

class CalendarPopoverController(http.Controller):

    @http.route('/calendar/edit_event', type='http', auth='user', website=True)
    def edit_event(self, event_id=None):
        if event_id:
            # Implement your logic to handle editing the event with the given event_id
            # Example: Fetch the event record and return a response
            event = request.env['technical.job'].browse(int(event_id))
            #import pdb;pdb.set_trace()
            if event:
                # Perform editing logic here
                # For example, you can return a JSON response or redirect to another page
                return request.render('calendar_extension.edit_event_success', {
                    'event': event,
                })
        # Handle errors or invalid requests
        return request.render('calendar_extension.edit_event_error')