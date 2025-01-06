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

   async onClickPrintTransactionBank() {
    try {

      const total_rec = await this.env.services.orm.searchRead('collection.services.commission',[],[]);
//      .then((result) => console.log(result)).catch((error) => console.log(error))

      let list_names = [];
      console.log('total_rec', total_rec);

      total_rec.forEach((name) => {
      console.log('NAME_37',name);
      if (!list_names.includes(name.name_account)){
      list_names.push(name.name_account);
      }
      });


      const all_rec = await this.env.services.orm.searchRead('list.name.account',[],[]);
      let list_all_rec = [];
      all_rec.forEach((rec) => {
      list_all_rec.push(rec.id);
      });

      const empty_list = this.env.services.orm.call('list.name.account','unlink',[list_all_rec]);

      console.log('LIST_NAMES_45',list_names)

      list_names.forEach((name) => {
      console.log('NOMBRE',name);
      this.env.services.orm.call('list.name.account','create',[{'name':name}])
      });

      this.action.doAction({
        name: 'Reporte de Movimientos bancarios',
        res_model: 'bank.movements.month.wiz',
        type: 'ir.actions.act_window',
        target: 'new',
        views: [[false, 'form']],
      });
    } catch (error) {
      console.error('Error en doAction:', error);
    }
  }

  async onClickRecalAll() {
    try {
      const result = await this.rpc("/web/dataset/call_kw/collection.transaction/recalculate_total_recs",{
        model: 'collection.transaction',
        method: 'recalculate_total_recs',
        args: [], // Argumentos específicos para el método Python
        kwargs: {}, // Argumentos clave-valor, si es necesario
      });
      console.log('Resultado de la función:', result);
    } catch (error) {
      console.error('Error en la llamada RPC:', error);
    }
  }
}

registry.category('views').add('button_print_transaction', {
  ...listView,
  Controller: CustomListController,
  buttonTemplate: 'payment_collection.ListButtons_Transaction',
});
