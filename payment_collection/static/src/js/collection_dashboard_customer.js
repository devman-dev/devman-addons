/** @odoo-module **/

import { ListController } from '@web/views/list/list_controller';
import { listView } from '@web/views/list/list_view';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';

class CustomListController extends ListController {
  setup() {
    super.setup();
    this.rpc = useService('rpc');
  }

  async onClickUpdateDashboard() {
    try {
      const result = await this.rpc("/web/dataset/call_kw/collection.dashboard.customer/update_available_balance",{
        model: 'collection.dashboard.customer',
        method: 'update_available_balance',
        args: [], // Argumentos específicos para el método Python
        kwargs: {}, // Argumentos clave-valor, si es necesario
      });
      console.log('Resultado de la función:', result);
    } catch (error) {
      console.error('Error en la llamada RPC:', error);
    }
  }
}

registry.category('views').add('button_update_dashboard', {
  ...listView,
  Controller: CustomListController,
  buttonTemplate: 'payment_collection.ListButtons',
});
