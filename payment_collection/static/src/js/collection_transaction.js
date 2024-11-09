/** @odoo-module **/

import { ListController } from '@web/views/list/list_controller';
import { listView } from '@web/views/list/list_view';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';

class CustomListController extends ListController {
  setup() {
    super.setup();
    this.action = useService("action");
  }

  async onClickPrintTransaction() {
    try {
      await this.action.doAction({
        name: 'Reporte de Cliente',
        res_model: 'commi.trans.wiz',
        type: 'ir.actions.act_window',
        target: 'new',
        views: [[false, 'form']],
      });
    } catch (error) {
      console.error('Error en doAction:', error);
    }
  }
}

registry.category('views').add('button_print_transaction', {
  ...listView,
  Controller: CustomListController,
  buttonTemplate: 'payment_collection.ListButtons_Transaction',
});
