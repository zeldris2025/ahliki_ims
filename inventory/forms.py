from django import forms
from .models import Product, Supplier, Category, GoodsReceivedNote, GRNItem, Sale, SaleItem, StockMovement


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['sku', 'name', 'category', 'supplier', 'unit_price', 'cost_price',
                  'reorder_level', 'unit', 'barcode', 'description', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'sku': forms.TextInput(attrs={'placeholder': 'e.g. ALW-RICE-25KG'}),
        }


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'contact_name', 'phone', 'email', 'address']
        widgets = {'address': forms.Textarea(attrs={'rows': 3})}


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description']
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}


class GRNForm(forms.ModelForm):
    class Meta:
        model = GoodsReceivedNote
        fields = ['grn_number', 'supplier', 'purchase_order', 'received_at', 'notes']
        widgets = {
            'received_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class GRNItemForm(forms.ModelForm):
    class Meta:
        model = GRNItem
        fields = ['product', 'quantity_received', 'batch_number', 'expiry_date', 'unit_cost']
        widgets = {
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
        }


GRNItemFormSet = forms.inlineformset_factory(
    GoodsReceivedNote, GRNItem,
    form=GRNItemForm, extra=3, can_delete=True
)


class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ['sale_number', 'customer_name', 'account_number', 'payment_method', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 2})}


class SaleItemForm(forms.ModelForm):
    class Meta:
        model = SaleItem
        fields = ['product', 'quantity', 'unit_price']


SaleItemFormSet = forms.inlineformset_factory(
    Sale, SaleItem,
    form=SaleItemForm, extra=3, can_delete=True
)


class StockAdjustForm(forms.ModelForm):
    class Meta:
        model = StockMovement
        fields = ['product', 'movement_type', 'quantity', 'notes', 'batch_number', 'expiry_date']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
        }
