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
odoo.define('custom_leads.TextWidget', function (require) {
    'use strict';

    const AbstractField = require('web.AbstractField');
    const field_registry = require('web.field_registry');
    const core = require('web.core');

    const _t = core._t;

    const TextWidget = AbstractField.extend({
        supportedFieldTypes: ['text'],

        /**
         * @override
         */
        _render: function () {
            this.$el.empty();
            const value = this.value || '';

            // Customize the maximum length before truncating the text
            const maxLength = 35;
            this.truncatedText = value.length > maxLength ? value.slice(0, maxLength) + '...' : value;

            // Create a container element for the text
            const $content = $('<div>', {
                class: 'o_text_widget',
                html: this.truncatedText,
            }).appendTo(this.$el);

            if (value.length > maxLength) {
                // Show "Ver más" button if the text is longer than the maximum length
                this.$seeMoreButton = $('<button>', {
                    class: 'o_btn_see_more btn btn-link',
                    text: _t('Ver más'),
                }).appendTo(this.$el);

                this.$seeMoreButton.click(this._onClickSeeMore.bind(this));
            }
        },

        /**
         * @private
         */
         _onClickSeeMore: function (ev) {
             if (this.$seeMoreButton.text() === _t('Ver más')) {
                 // Show the full text when clicking "Ver más"
                 const fullText = this.value || '';
                 this.$el.find('.o_text_widget').html(fullText);
                 this.$seeMoreButton.text(_t('Ver menos'));
             } else {
                 // Truncate the text again and show "Ver más" when clicking "Ver menos"
                 this.$el.find('.o_text_widget').html(this.truncatedText);
                 this.$seeMoreButton.text(_t('Ver más'));
                 this._triggerResizeEvent(); // Trigger resize when clicking "Ver menos"
             }
             this.trigger_up('widgets_start_request', {editableMode: true});
         },

        /**
         * @override
         */
        _renderEdit: function () {
            this.$el.removeClass('o_text_widget');
            this._super.apply(this, arguments);
            if (this.$seeMoreButton && this.value.length <= 35) {
                this.$seeMoreButton.hide();
            }
        },

        /**
         * @private
         * Triggers the 'resize' event on the table to adjust column width
         */
        _triggerResizeEvent: function () {
            const $table = this.$el.closest('.o_list_view').find('.o_list_table');
            $table.trigger('resize');
        },
    });

    field_registry.add('text_widget', TextWidget);

    return TextWidget;
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