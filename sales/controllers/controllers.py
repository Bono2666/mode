# from odoo import http


# class Sales(http.Controller):
#     @http.route('/sales/sales', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/sales/sales/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('sales.listing', {
#             'root': '/sales/sales',
#             'objects': http.request.env['sales.sales'].search([]),
#         })

#     @http.route('/sales/sales/objects/<model("sales.sales"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('sales.object', {
#             'object': obj
#         })

