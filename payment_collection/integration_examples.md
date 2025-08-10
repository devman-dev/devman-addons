# Ejemplos de Integración - Collection Transaction API

## Python Example

```python
import requests
import json
from datetime import datetime, date

class CollectionAPI:
    def __init__(self, base_url, api_key):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
    
    def create_transaction(self, transaction_data):
        """Crear una nueva transacción"""
        url = f"{self.base_url}/api/collection/transactions"
        response = requests.post(url, json=transaction_data, headers=self.headers)
        return response.json()
    
    def get_transactions(self, filters=None):
        """Obtener lista de transacciones"""
        url = f"{self.base_url}/api/collection/transactions"
        params = filters or {}
        response = requests.get(url, params=params, headers=self.headers)
        return response.json()
    
    def get_customer_balance(self, customer_id):
        """Obtener saldo de cliente"""
        url = f"{self.base_url}/api/collection/customers/{customer_id}/balance"
        response = requests.get(url, headers=self.headers)
        return response.json()
    
    def generate_report(self, customer_id, date_from, date_to):
        """Generar reporte de transacciones"""
        url = f"{self.base_url}/api/collection/reports/transactions"
        data = {
            'customer_id': customer_id,
            'date_from': date_from,
            'date_to': date_to,
            'format': 'pdf'
        }
        response = requests.post(url, json=data, headers=self.headers)
        return response.json()

# Ejemplo de uso
if __name__ == "__main__":
    # Configuración
    api = CollectionAPI(
        base_url="https://tu-instancia-odoo.com",
        api_key="your-api-key-here"
    )
    
    # 1. Crear una transacción
    new_transaction = {
        "customer_id": 123,
        "amount": 1500.75,
        "date": "2025-08-03",
        "collection_trans_type": "movimiento_recaudacion",
        "service_id": 45,
        "operation_id": 67,
        "description": "Pago de servicios empresariales",
        "currency_id": 1,
        "origin_type": "externo",
        "origin_account": {
            "cuit": "20123456789",
            "cbu": "0123456789012345678901",
            "alias": "empresa.principal",
            "name": "Cuenta Principal Empresa"
        },
        "destination_account": {
            "cuit": "27987654321",
            "cbu": "9876543210987654321098",
            "alias": "destino.servicios",
            "name": "Cuenta Servicios"
        },
        "commission": 2.5,
        "categories": [1, 2]
    }
    
    result = api.create_transaction(new_transaction)
    print("Transacción creada:", result)
    
    # 2. Consultar transacciones del cliente
    filters = {
        "customer_id": 123,
        "date_from": "2025-07-01",
        "date_to": "2025-08-03",
        "limit": 20
    }
    
    transactions = api.get_transactions(filters)
    print(f"Encontradas {transactions['data']['total_count']} transacciones")
    
    # 3. Obtener saldo del cliente
    balance = api.get_customer_balance(123)
    print("Saldo del cliente:", balance['data']['balances'])
    
    # 4. Generar reporte
    report = api.generate_report(123, "2025-07-01", "2025-07-31")
    if report['success']:
        print(f"Reporte generado: {report['data']['report_url']}")
```

## JavaScript/Node.js Example

```javascript
const axios = require('axios');

class CollectionAPI {
    constructor(baseUrl, apiKey) {
        this.baseUrl = baseUrl.replace(/\/$/, '');
        this.headers = {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${apiKey}`
        };
    }
    
    async createTransaction(transactionData) {
        try {
            const response = await axios.post(
                `${this.baseUrl}/api/collection/transactions`,
                transactionData,
                { headers: this.headers }
            );
            return response.data;
        } catch (error) {
            throw new Error(`Error creating transaction: ${error.response?.data?.error?.message || error.message}`);
        }
    }
    
    async getTransactions(filters = {}) {
        try {
            const response = await axios.get(
                `${this.baseUrl}/api/collection/transactions`,
                { 
                    params: filters,
                    headers: this.headers 
                }
            );
            return response.data;
        } catch (error) {
            throw new Error(`Error getting transactions: ${error.response?.data?.error?.message || error.message}`);
        }
    }
    
    async getCustomerBalance(customerId) {
        try {
            const response = await axios.get(
                `${this.baseUrl}/api/collection/customers/${customerId}/balance`,
                { headers: this.headers }
            );
            return response.data;
        } catch (error) {
            throw new Error(`Error getting balance: ${error.response?.data?.error?.message || error.message}`);
        }
    }
    
    async updateTransactionStatus(transactionId, newStatus) {
        try {
            const response = await axios.patch(
                `${this.baseUrl}/api/collection/transactions/${transactionId}/status`,
                { transaction_state: newStatus },
                { headers: this.headers }
            );
            return response.data;
        } catch (error) {
            throw new Error(`Error updating status: ${error.response?.data?.error?.message || error.message}`);
        }
    }
    
    async getAnalytics(filters = {}) {
        try {
            const response = await axios.get(
                `${this.baseUrl}/api/collection/reports/transaction-analytics`,
                { 
                    params: filters,
                    headers: this.headers 
                }
            );
            return response.data;
        } catch (error) {
            throw new Error(`Error getting analytics: ${error.response?.data?.error?.message || error.message}`);
        }
    }
}

// Ejemplo de uso
async function main() {
    const api = new CollectionAPI(
        'https://tu-instancia-odoo.com',
        'your-api-key-here'
    );
    
    try {
        // 1. Crear transacción
        const newTransaction = {
            customer_id: 123,
            amount: 2500.00,
            date: '2025-08-03',
            collection_trans_type: 'movimiento_recaudacion',
            service_id: 45,
            description: 'Pago mensual de servicios',
            currency_id: 1,
            origin_account: {
                cuit: '20123456789',
                cbu: '0123456789012345678901',
                alias: 'cuenta.empresa',
                name: 'Cuenta Empresarial'
            }
        };
        
        const result = await api.createTransaction(newTransaction);
        console.log('Transacción creada:', result);
        
        // 2. Consultar analytics
        const analytics = await api.getAnalytics({
            date_from: '2025-07-01',
            date_to: '2025-08-03'
        });
        
        console.log('Analytics:', {
            totalTransactions: analytics.data.summary.total_transactions,
            totalAmount: analytics.data.summary.total_amount,
            topCustomers: analytics.data.top_customers.slice(0, 3)
        });
        
        // 3. Actualizar estado de transacción
        if (result.success) {
            const statusUpdate = await api.updateTransactionStatus(
                result.data.id, 
                'aprobado'
            );
            console.log('Estado actualizado:', statusUpdate);
        }
        
    } catch (error) {
        console.error('Error:', error.message);
    }
}

main();
```

## PHP Example

```php
<?php

class CollectionAPI {
    private $baseUrl;
    private $headers;
    
    public function __construct($baseUrl, $apiKey) {
        $this->baseUrl = rtrim($baseUrl, '/');
        $this->headers = [
            'Content-Type: application/json',
            'Authorization: Bearer ' . $apiKey
        ];
    }
    
    public function createTransaction($transactionData) {
        $url = $this->baseUrl . '/api/collection/transactions';
        return $this->makeRequest('POST', $url, $transactionData);
    }
    
    public function getTransactions($filters = []) {
        $url = $this->baseUrl . '/api/collection/transactions';
        if (!empty($filters)) {
            $url .= '?' . http_build_query($filters);
        }
        return $this->makeRequest('GET', $url);
    }
    
    public function getCustomerBalance($customerId) {
        $url = $this->baseUrl . '/api/collection/customers/' . $customerId . '/balance';
        return $this->makeRequest('GET', $url);
    }
    
    public function createService($serviceData) {
        $url = $this->baseUrl . '/api/collection/services';
        return $this->makeRequest('POST', $url, $serviceData);
    }
    
    public function getCommissionSummary($filters = []) {
        $url = $this->baseUrl . '/api/collection/reports/commission-summary';
        if (!empty($filters)) {
            $url .= '?' . http_build_query($filters);
        }
        return $this->makeRequest('GET', $url);
    }
    
    private function makeRequest($method, $url, $data = null) {
        $curl = curl_init();
        
        curl_setopt_array($curl, [
            CURLOPT_URL => $url,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CUSTOMREQUEST => $method,
            CURLOPT_HTTPHEADER => $this->headers,
            CURLOPT_SSL_VERIFYPEER => false,
            CURLOPT_TIMEOUT => 30
        ]);
        
        if ($data && in_array($method, ['POST', 'PUT', 'PATCH'])) {
            curl_setopt($curl, CURLOPT_POSTFIELDS, json_encode($data));
        }
        
        $response = curl_exec($curl);
        $httpCode = curl_getinfo($curl, CURLINFO_HTTP_CODE);
        $error = curl_error($curl);
        
        curl_close($curl);
        
        if ($error) {
            throw new Exception("cURL Error: " . $error);
        }
        
        $decodedResponse = json_decode($response, true);
        
        if ($httpCode >= 400) {
            $errorMessage = $decodedResponse['error']['message'] ?? 'Unknown error';
            throw new Exception("API Error ($httpCode): " . $errorMessage);
        }
        
        return $decodedResponse;
    }
}

// Ejemplo de uso
try {
    $api = new CollectionAPI(
        'https://tu-instancia-odoo.com',
        'your-api-key-here'
    );
    
    // 1. Crear un nuevo servicio
    $newService = [
        'customer_id' => 123,
        'service_id' => 78,
        'commission' => 3.5,
        'commission_app_rate' => 1.2,
        'name_account' => 'Cuenta de Servicios Premium',
        'bank_id' => 12,
        'cbu' => '0123456789012345678901',
        'cvu' => '0000003100012345678912',
        'alias' => 'servicios.premium',
        'cuit' => '20987654321',
        'agent_commissions' => [
            [
                'agent_id' => 34,
                'commission_rate' => 0.8
            ]
        ]
    ];
    
    $serviceResult = $api->createService($newService);
    echo "Servicio creado: " . json_encode($serviceResult) . "\n";
    
    // 2. Crear transacción usando el servicio
    $newTransaction = [
        'customer_id' => 123,
        'amount' => 5000.00,
        'date' => '2025-08-03',
        'collection_trans_type' => 'movimiento_recaudacion',
        'service_id' => $serviceResult['data']['id'],
        'operation_id' => 67,
        'description' => 'Transacción de prueba PHP',
        'currency_id' => 1,
        'origin_account' => [
            'cuit' => '20123456789',
            'cbu' => '0123456789012345678901',
            'alias' => 'cuenta.php.test',
            'name' => 'Cuenta Test PHP'
        ]
    ];
    
    $transactionResult = $api->createTransaction($newTransaction);
    echo "Transacción creada: " . json_encode($transactionResult) . "\n";
    
    // 3. Consultar saldo del cliente
    $balance = $api->getCustomerBalance(123);
    echo "Saldo del cliente: " . json_encode($balance['data']['balances']) . "\n";
    
    // 4. Obtener resumen de comisiones
    $commissions = $api->getCommissionSummary([
        'date_from' => '2025-07-01',
        'date_to' => '2025-08-03',
        'customer_id' => 123
    ]);
    
    echo "Resumen de comisiones: " . json_encode($commissions['data']['summary']) . "\n";
    
} catch (Exception $e) {
    echo "Error: " . $e->getMessage() . "\n";
}
?>
```

## C# Example

```csharp
using System;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using Newtonsoft.Json;
using System.Collections.Generic;

public class CollectionAPI
{
    private readonly HttpClient _httpClient;
    private readonly string _baseUrl;
    
    public CollectionAPI(string baseUrl, string apiKey)
    {
        _baseUrl = baseUrl.TrimEnd('/');
        _httpClient = new HttpClient();
        _httpClient.DefaultRequestHeaders.Add("Authorization", $"Bearer {apiKey}");
        _httpClient.DefaultRequestHeaders.Add("Accept", "application/json");
    }
    
    public async Task<ApiResponse<TransactionCreateResponse>> CreateTransactionAsync(TransactionCreateRequest request)
    {
        var json = JsonConvert.SerializeObject(request);
        var content = new StringContent(json, Encoding.UTF8, "application/json");
        
        var response = await _httpClient.PostAsync($"{_baseUrl}/api/collection/transactions", content);
        var responseString = await response.Content.ReadAsStringAsync();
        
        return JsonConvert.DeserializeObject<ApiResponse<TransactionCreateResponse>>(responseString);
    }
    
    public async Task<ApiResponse<TransactionListResponse>> GetTransactionsAsync(TransactionFilters filters = null)
    {
        var queryParams = BuildQueryString(filters);
        var url = $"{_baseUrl}/api/collection/transactions{queryParams}";
        
        var response = await _httpClient.GetAsync(url);
        var responseString = await response.Content.ReadAsStringAsync();
        
        return JsonConvert.DeserializeObject<ApiResponse<TransactionListResponse>>(responseString);
    }
    
    public async Task<ApiResponse<CustomerBalance>> GetCustomerBalanceAsync(int customerId)
    {
        var response = await _httpClient.GetAsync($"{_baseUrl}/api/collection/customers/{customerId}/balance");
        var responseString = await response.Content.ReadAsStringAsync();
        
        return JsonConvert.DeserializeObject<ApiResponse<CustomerBalance>>(responseString);
    }
    
    public async Task<ApiResponse<AnalyticsResponse>> GetAnalyticsAsync(AnalyticsFilters filters = null)
    {
        var queryParams = BuildQueryString(filters);
        var url = $"{_baseUrl}/api/collection/reports/transaction-analytics{queryParams}";
        
        var response = await _httpClient.GetAsync(url);
        var responseString = await response.Content.ReadAsStringAsync();
        
        return JsonConvert.DeserializeObject<ApiResponse<AnalyticsResponse>>(responseString);
    }
    
    private string BuildQueryString(object filters)
    {
        if (filters == null) return "";
        
        var properties = filters.GetType().GetProperties();
        var queryParams = new List<string>();
        
        foreach (var prop in properties)
        {
            var value = prop.GetValue(filters);
            if (value != null)
            {
                queryParams.Add($"{prop.Name}={Uri.EscapeDataString(value.ToString())}");
            }
        }
        
        return queryParams.Count > 0 ? "?" + string.Join("&", queryParams) : "";
    }
    
    public void Dispose()
    {
        _httpClient?.Dispose();
    }
}

// Modelos de datos
public class ApiResponse<T>
{
    public bool Success { get; set; }
    public T Data { get; set; }
    public string Message { get; set; }
    public ApiError Error { get; set; }
}

public class ApiError
{
    public string Code { get; set; }
    public string Message { get; set; }
}

public class TransactionCreateRequest
{
    public int CustomerId { get; set; }
    public decimal Amount { get; set; }
    public string Date { get; set; }
    public string CollectionTransType { get; set; }
    public int? ServiceId { get; set; }
    public int? OperationId { get; set; }
    public string Description { get; set; }
    public int? CurrencyId { get; set; }
    public AccountInfo OriginAccount { get; set; }
    public AccountInfo DestinationAccount { get; set; }
    public decimal? Commission { get; set; }
    public List<int> Categories { get; set; }
}

public class AccountInfo
{
    public string Cuit { get; set; }
    public string Cbu { get; set; }
    public string Cvu { get; set; }
    public string Alias { get; set; }
    public string Name { get; set; }
}

public class TransactionCreateResponse
{
    public int Id { get; set; }
    public string TransactionName { get; set; }
    public string Status { get; set; }
    public decimal CommissionAmount { get; set; }
    public decimal RealBalance { get; set; }
    public decimal AvailableBalance { get; set; }
}

public class TransactionListResponse
{
    public List<Transaction> Transactions { get; set; }
    public int TotalCount { get; set; }
    public bool HasNext { get; set; }
}

public class Transaction
{
    public int Id { get; set; }
    public string TransactionName { get; set; }
    public decimal Amount { get; set; }
    public string Date { get; set; }
    public string CollectionTransType { get; set; }
    public string TransactionState { get; set; }
    public string Description { get; set; }
}

public class CustomerBalance
{
    public int CustomerId { get; set; }
    public BalanceInfo Balances { get; set; }
    public Dictionary<string, decimal> CurrencyBalances { get; set; }
    public string LastUpdated { get; set; }
}

public class BalanceInfo
{
    public decimal TotalBalance { get; set; }
    public decimal AvailableBalance { get; set; }
    public decimal RealBalance { get; set; }
}

public class TransactionFilters
{
    public int? CustomerId { get; set; }
    public string DateFrom { get; set; }
    public string DateTo { get; set; }
    public string TransactionState { get; set; }
    public int? Limit { get; set; }
    public int? Offset { get; set; }
}

public class AnalyticsFilters
{
    public string DateFrom { get; set; }
    public string DateTo { get; set; }
    public int? CustomerId { get; set; }
}

public class AnalyticsResponse
{
    public AnalyticsSummary Summary { get; set; }
    public Dictionary<string, TypeAnalytics> ByTransactionType { get; set; }
    public Dictionary<string, TypeAnalytics> ByState { get; set; }
    public List<CustomerAnalytics> TopCustomers { get; set; }
}

public class AnalyticsSummary
{
    public int TotalTransactions { get; set; }
    public decimal TotalAmount { get; set; }
    public decimal AverageTransaction { get; set; }
}

public class TypeAnalytics
{
    public int Count { get; set; }
    public decimal TotalAmount { get; set; }
    public decimal AverageAmount { get; set; }
}

public class CustomerAnalytics
{
    public string Name { get; set; }
    public int CustomerId { get; set; }
    public int TransactionCount { get; set; }
    public decimal TotalAmount { get; set; }
}

// Ejemplo de uso
class Program
{
    static async Task Main(string[] args)
    {
        var api = new CollectionAPI(
            "https://tu-instancia-odoo.com",
            "your-api-key-here"
        );
        
        try
        {
            // 1. Crear transacción
            var newTransaction = new TransactionCreateRequest
            {
                CustomerId = 123,
                Amount = 1750.50m,
                Date = "2025-08-03",
                CollectionTransType = "movimiento_recaudacion",
                ServiceId = 45,
                OperationId = 67,
                Description = "Transacción desde C#",
                CurrencyId = 1,
                OriginAccount = new AccountInfo
                {
                    Cuit = "20123456789",
                    Cbu = "0123456789012345678901",
                    Alias = "cuenta.csharp",
                    Name = "Cuenta C# Test"
                },
                Categories = new List<int> { 1, 2 }
            };
            
            var result = await api.CreateTransactionAsync(newTransaction);
            
            if (result.Success)
            {
                Console.WriteLine($"Transacción creada: {result.Data.TransactionName}");
                Console.WriteLine($"ID: {result.Data.Id}");
                Console.WriteLine($"Saldo disponible: {result.Data.AvailableBalance:C}");
            }
            else
            {
                Console.WriteLine($"Error: {result.Error.Message}");
            }
            
            // 2. Consultar transacciones
            var filters = new TransactionFilters
            {
                CustomerId = 123,
                DateFrom = "2025-07-01",
                DateTo = "2025-08-03",
                Limit = 10
            };
            
            var transactions = await api.GetTransactionsAsync(filters);
            
            if (transactions.Success)
            {
                Console.WriteLine($"Encontradas {transactions.Data.TotalCount} transacciones");
                foreach (var transaction in transactions.Data.Transactions)
                {
                    Console.WriteLine($"- {transaction.TransactionName}: {transaction.Amount:C}");
                }
            }
            
            // 3. Obtener analytics
            var analyticsFilters = new AnalyticsFilters
            {
                DateFrom = "2025-07-01",
                DateTo = "2025-08-03"
            };
            
            var analytics = await api.GetAnalyticsAsync(analyticsFilters);
            
            if (analytics.Success)
            {
                Console.WriteLine($"Total transacciones: {analytics.Data.Summary.TotalTransactions}");
                Console.WriteLine($"Monto total: {analytics.Data.Summary.TotalAmount:C}");
                Console.WriteLine($"Promedio: {analytics.Data.Summary.AverageTransaction:C}");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error: {ex.Message}");
        }
        finally
        {
            api.Dispose();
        }
    }
}
```

## Webhook Handler Example (Python Flask)

```python
from flask import Flask, request, jsonify
import hashlib
import hmac
import json
from datetime import datetime

app = Flask(__name__)

# Configuración del webhook
WEBHOOK_SECRET = "your-webhook-secret-key"

def verify_webhook_signature(payload_body, signature_header):
    """Verificar la firma del webhook"""
    if not signature_header:
        return False
    
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode('utf-8'),
        payload_body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(f"sha256={expected_signature}", signature_header)

@app.route('/webhook/collection-events', methods=['POST'])
def handle_collection_webhook():
    """Manejar eventos del webhook de transacciones"""
    try:
        # Verificar firma
        signature = request.headers.get('X-Signature-256')
        if not verify_webhook_signature(request.data, signature):
            return jsonify({'error': 'Invalid signature'}), 401
        
        # Parsear datos
        event_data = request.json
        event_type = event_data.get('event')
        timestamp = event_data.get('timestamp')
        data = event_data.get('data', {})
        
        print(f"Received webhook event: {event_type} at {timestamp}")
        
        # Procesar según el tipo de evento
        if event_type == 'transaction.created':
            handle_transaction_created(data)
        elif event_type == 'transaction.updated':
            handle_transaction_updated(data)
        elif event_type == 'transaction.state_changed':
            handle_transaction_state_changed(data)
        elif event_type == 'balance.updated':
            handle_balance_updated(data)
        else:
            print(f"Unknown event type: {event_type}")
        
        return jsonify({'status': 'success', 'message': 'Event processed'}), 200
        
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

def handle_transaction_created(data):
    """Manejar evento de transacción creada"""
    transaction_id = data.get('transaction_id')
    customer_id = data.get('customer_id')
    amount = data.get('amount')
    
    print(f"Nueva transacción creada: ID={transaction_id}, Cliente={customer_id}, Monto={amount}")
    
    # Aquí puedes agregar tu lógica de negocio:
    # - Enviar notificaciones
    # - Actualizar sistemas externos
    # - Registrar en logs
    # - Etc.

def handle_transaction_updated(data):
    """Manejar evento de transacción actualizada"""
    transaction_id = data.get('transaction_id')
    print(f"Transacción actualizada: ID={transaction_id}")

def handle_transaction_state_changed(data):
    """Manejar evento de cambio de estado"""
    transaction_id = data.get('transaction_id')
    old_state = data.get('old_state')
    new_state = data.get('new_state')
    
    print(f"Estado cambiado: ID={transaction_id}, {old_state} -> {new_state}")
    
    # Lógica específica para cambios de estado
    if new_state == 'aprobado':
        # Procesar aprobación
        pass
    elif new_state == 'rechazado':
        # Procesar rechazo
        pass

def handle_balance_updated(data):
    """Manejar evento de actualización de saldo"""
    customer_id = data.get('customer_id')
    new_balance = data.get('new_balance')
    
    print(f"Saldo actualizado: Cliente={customer_id}, Nuevo saldo={new_balance}")

if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

Estos ejemplos proporcionan una base sólida para integrar con la API de Collection Transaction en diferentes lenguajes de programación y incluyen manejo de errores, autenticación y ejemplos de uso común.
