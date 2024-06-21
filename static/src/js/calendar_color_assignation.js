odoo.define('calendar_extension.CalendarPopoverExtension', function (require) {
    "use strict";

    var CalendarPopover = require('web.CalendarPopover');
    var core = require('web.core');

    var _t = core._t;

    var CalendarPopoverExtension = CalendarPopover.extend({
        events: _.extend({}, CalendarPopover.prototype.events, {
            'click .o_cw_popover_done': '_onClickPopoverDone',
        }),

        /**
         * @override
         */
        start: function () {
            return this._super.apply(this, arguments).then(this._renderDoneButton.bind(this));
        },

        /**
         * @private
         * Renders the "Done" button in the popover
         */
        _renderDoneButton: function () {
            var $button = $('<a>', {
                href: '#',
                class: 'btn btn-secondary o_cw_popover_done',
                text: _t('Done'),
            });
            this.$('.o_cw_popover_buttons').append($button);
        },

        /**
         * @private
         * Handle click event on "Done" button
         * @param {jQueryEvent} ev
         */
        _onClickPopoverDone: function (ev) {
            ev.preventDefault();
            console.log('Clicked Done button!'); // Debug statement
            this._onDone();
        },

        /**
         * @private
         * Action to perform when "Done" button is clicked
         */
        _onDone: function () {
            console.log('Executing _onDone'); // Debug statement
            this.trigger_up('new_event_clicked', {
                modelName: this.modelName,
            });
        },
    });

    return CalendarPopoverExtension;
});
