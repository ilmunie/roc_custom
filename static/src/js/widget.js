odoo.define('custom_leads.Many2oneOpenTabWidget', function (require) {
    'use strict';

    var AbstractField = require('web.AbstractField');
    var field_registry = require('web.field_registry');
    var core = require('web.core');
    var config = require('web.config');

    var Many2oneOpenTabWidget = AbstractField.extend({
        supportedFieldTypes: ['many2one'],
        events: {
            'click': '_onClick',
        },

        /**
         * @private
         * @returns {string} URL to open the many2one record in form view.
         */
        _getReference_m2one: function () {
            var url = window.location.href;
            var searchParams = new URLSearchParams(url.split("#")[1]);
            searchParams.set("view_type", "form");
            searchParams.set("id", this.value.res_id);
            searchParams.set("model", this.field.relation);
            searchParams.set("action", "custom_leads.crm_debt_co_sales");

       
            return url.split("#")[0] + "#" + searchParams.toString();
        },

        /**
         * @override
         * @private
         */
        _renderReadonly: function () {
            var $content = $('<div>', {
                class: 'many2one_open_tab_widget',
            });
        
            var $link = $('<a>', {
                href: this._getReference_m2one(),

            });
        
            var $text = $('<span>', {
                text: ' Venta   ',
            });
            var $icon = $('<i>', {
                class: 'fa fa-external-link',
            });
        
            $content.append($link).append($text).append($icon);
            this.$el.append($content);
        },

        /**
         * @private
         * @param {Event} ev
         */
        _onClick: function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            window.open(this._getReference_m2one());
        },
    });

    field_registry.add('many2one_open_tab', Many2oneOpenTabWidget);

    return Many2oneOpenTabWidget;
});



odoo.define('custom_leads.CopyPhoneWidget', function (require) {
    'use strict';

    var AbstractField = require('web.AbstractField');
    var field_registry = require('web.field_registry');
    var core = require('web.core');

    var CopyPhoneWidget = AbstractField.extend({
        supportedFieldTypes: ['char'],
        events: {
            'click .o_field_widget .fa-copy': '_onClickCopy',
        },

        /**
         * @private
         */
        _renderReadonly: function () {
            var $content = $('<div>', {
                class: 'o_field_widget o_copy_phone_widget',
            });
        
            var $value = $('<span>', {
                class: 'o_field_widget_char',
                text: '   ' + this.value,
            });
        
            var $link = $('<a>', {
                href: '#',
            });
        
            var $icon = $('<i>', {
                class: 'fa fa-copy',
            });
        
            $content.append($icon).append($value);
            this.$el.append($content);
        },

        /**
         * @private
         * @param {Event} ev
         */
        _onClickCopy: function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            var phoneValue = this.value;
            if (phoneValue) {
                navigator.clipboard.writeText(phoneValue).then(function () {
                    console.log('Phone number copied to clipboard: ' + phoneValue);
                    var $notif = $('<div>', {
                        class: 'o_notification_warning',
                        text: 'N° teléfono copiado: ' + phoneValue,
                    });
                    $('header').append($notif);
                    setTimeout(function () {
                        $notif.remove();
                    }, 3000);
                }, function (err) {
                    console.error('Failed to copy phone number to clipboard: ' + err);
                });
            }
        },
    });

    field_registry.add('copy_phone', CopyPhoneWidget);

    return CopyPhoneWidget;
});


odoo.define('many2many_tags_link.widget', function (require) {
"use strict";

	var core = require('web.core');
	var AbstractField = require('web.AbstractField');
	var registry = require('web.field_registry');
	var relational_fields = require('web.relational_fields');

	var _t = core._t;
	var qweb = core.qweb;

	var FieldMany2ManyTagsLink = relational_fields.FieldMany2ManyTags.extend({
		tag_template: "FieldMany2ManyTagsLink",
		events: _.extend({}, AbstractField.prototype.events, {
	        'click .o_delete': '_onDeleteTag',
	        'click .o_external_link': '_openRelated',
	    }),
		_openRelated: function (event) {
	        event.preventDefault();
	        event.stopPropagation();
	        var self = this;

	        var modelid = parseInt(event.currentTarget.getAttribute('modelid'));

	        if (this.mode === 'readonly' && !this.noOpen && modelid) {
	            this._rpc({
	                    model: this.field.relation,
	                    method: 'get_formview_action',
	                    args: [[modelid]],
	                    context: this.record.getContext(this.recordParams),
	                })
	                .then(function (action) {
	                    self.trigger_up('do_action', {action: action});
	                });
	        }
	    },

	});


	registry
    .add('many2many_tags_link', FieldMany2ManyTagsLink);

    return {
    	FieldMany2ManyTagsLink: FieldMany2ManyTagsLink,
	}

});