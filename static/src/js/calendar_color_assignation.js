/** @odoo-module **/

import CalendarRenderer from 'web.CalendarRenderer';

const CustomCalendarRenderer = CalendarRenderer.extend({
    /**
     * Override the getColor function to make all colors red.
     * @override
     */
    getColor: function (key) {
        return '#FF0000';  // Set all colors to red
    },
});

export default CustomCalendarRenderer;