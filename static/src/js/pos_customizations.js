odoo.define('roc_custom.POSModelOverride', function (require) {
    "use strict";
    var models = require('point_of_sale.models');
    models.load_fields('product.product', ['pos_force_ship_later']);
});

odoo.define('roc_custom.POSValidateOverride', function(require) {
    'use strict';

    const PaymentScreen = require('point_of_sale.PaymentScreen');
    const Registries = require('point_of_sale.Registries');

    const POSValidateOverride = PaymentScreen =>
        class extends PaymentScreen {
            /**
             * @override
             */
            async validateOrder(isForceValidate) {
                const orderLines = this.currentOrder.get_orderlines();
                const containsForceShipLater = orderLines.some(line => line.product && line.product.pos_force_ship_later);
                if (containsForceShipLater && !this.currentOrder.is_to_ship()) {
                    this.showPopup('ErrorPopup', {
                        title: this.env._t('Error de validación de Orden'),
                        body: this.env._t('El pedido contiene productos que deben ser enviados más tarde'),
                    });
                    return false;
                }
                if (this.currentOrder.get_due() <= 0 && this.currentOrder.is_to_ship() && this.currentOrder.get_client() && !this.currentOrder.is_to_invoice()) {
                    return await this._finalizeValidation();
                }
                if (this.currentOrder.get_due() > 0 ) {
                    this.showPopup('ErrorPopup', {
                        title: this.env._t('Error de pago'),
                        body: this.env._t('Por favor, seleccione un medio de pago'),
                    });
                    return false;
                }
                super.validateOrder(isForceValidate);
            }
        };

    Registries.Component.extend(PaymentScreen, POSValidateOverride);

    return PaymentScreen;
});
