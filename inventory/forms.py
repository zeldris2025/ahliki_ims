from django import forms
from .models import (Product, Supplier, Category, GoodsReceivedNote, GRNItem, Sale, SaleItem,
                     StockMovement, Pallet, ShelfLocation, Invoice, Container, ContainerItem,
                     ContainerComment, ContainerType)


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
        fields = ['supplier', 'received_at', 'notes']
        widgets = {
            'received_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Container number, delivery notes, any remarks…'}),
        }


class GRNItemForm(forms.ModelForm):
    class Meta:
        model = GRNItem
        fields = ['product', 'quantity_received', 'expiry_date']
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


# ── WMS Forms ─────────────────────────────────────────────────────────────────

class PalletForm(forms.ModelForm):
    class Meta:
        model = Pallet
        fields = ['product', 'quantity', 'expiry_date', 'grn_item', 'notes']
        widgets = {
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, grn=None, **kwargs):
        super().__init__(*args, **kwargs)
        if grn:
            self.fields['grn_item'].queryset = GRNItem.objects.filter(grn=grn)
            self.fields['grn_item'].required = False
        else:
            self.fields['grn_item'].queryset = GRNItem.objects.select_related('grn', 'product').order_by('-grn__received_at')
            self.fields['grn_item'].required = False


class CheckInForm(forms.Form):
    lot_number = forms.CharField(
        max_length=100,
        label='Pallet Lot Number',
        widget=forms.TextInput(attrs={'placeholder': 'Scan QR or type lot number', 'autocomplete': 'off'}),
    )
    shelf = forms.ModelChoiceField(
        queryset=ShelfLocation.objects.all(),
        label='Shelf Location',
        empty_label='— select shelf —',
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))


class TransferForm(forms.Form):
    lot_number = forms.CharField(
        max_length=100,
        label='Pallet Lot Number',
        widget=forms.TextInput(attrs={'placeholder': 'Scan QR or type lot number', 'autocomplete': 'off'}),
    )
    to_shelf = forms.ModelChoiceField(
        queryset=ShelfLocation.objects.all(),
        label='Transfer To Shelf',
        empty_label='— select destination shelf —',
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))


class PalletEditForm(forms.ModelForm):
    class Meta:
        model = Pallet
        fields = ['quantity', 'expiry_date', 'notes']
        widgets = {
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional remarks…'}),
        }


class InvoiceUploadForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = [
            'invoice_number', 'customer_name', 'account_number',
            'salesperson', 'payment_method', 'payment_terms',
            'sales_territory', 'due_date', 'total_amount', 'tax_amount',
            'notes', 'invoice_file',
        ]
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Any remarks…'}),
            'invoice_number': forms.TextInput(attrs={'placeholder': 'e.g. 72928'}),
            'customer_name': forms.TextInput(attrs={'placeholder': 'e.g. Taumeasina Resort'}),
            'account_number': forms.TextInput(attrs={'placeholder': 'e.g. TWN-001'}),
            'salesperson': forms.TextInput(attrs={'placeholder': 'e.g. Ropati'}),
            'payment_terms': forms.TextInput(attrs={'placeholder': 'e.g. Net 7 days'}),
            'sales_territory': forms.TextInput(attrs={'placeholder': 'e.g. TWN'}),
        }
        labels = {
            'invoice_file': 'Invoice PDF',
            'total_amount': 'Total (Incl. VAT)',
            'tax_amount': '15% VAT Amount',
        }


# ── Container Forms (Customs Broker + Warehouse) ─────────────────────────────

class ContainerForm(forms.ModelForm):
    class Meta:
        model = Container
        fields = ['container_number', 'container_type', 'vessel', 'arrival_date', 'supplier', 'notes']
        widgets = {
            'arrival_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Clearance remarks, seal number, anything worth noting…'}),
            'container_number': forms.TextInput(attrs={'placeholder': 'e.g. MSKU1234567', 'autocomplete': 'off'}),
            'vessel': forms.TextInput(attrs={'placeholder': 'e.g. Southern Moana V.24'}),
        }
        labels = {'arrival_date': 'Wharf arrival date'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A supplier is needed so the GRN can be raised when the container is opened.
        self.fields['supplier'].required = True
        self.fields['supplier'].empty_label = '— select supplier —'
        # Only offer container types that are still in use; maintained in the admin panel.
        self.fields['container_type'].queryset = ContainerType.objects.filter(is_active=True)
        self.fields['container_type'].empty_label = '— select container type —'

    def clean_container_number(self):
        return self.cleaned_data['container_number'].strip().upper()


class ContainerItemForm(forms.ModelForm):
    class Meta:
        model = ContainerItem
        fields = ['product', 'quantity', 'expiry_date', 'notes']
        widgets = {
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.TextInput(attrs={'placeholder': 'Optional'}),
        }
        labels = {'expiry_date': 'Expiry date (optional)'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(is_active=True).order_by('name')

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if qty is not None and qty < 1:
            raise forms.ValidationError('Quantity must be at least 1.')
        return qty


ContainerItemFormSet = forms.inlineformset_factory(
    Container, ContainerItem,
    form=ContainerItemForm, extra=3, can_delete=True
)


class ContainerCommentForm(forms.ModelForm):
    class Meta:
        model = ContainerComment
        fields = ['body', 'is_damage']
        widgets = {
            'body': forms.Textarea(attrs={'rows': 3, 'placeholder': 'e.g. 3 cartons crushed on the top layer — set aside for claim.'}),
        }
        labels = {'body': 'Comment', 'is_damage': 'Flag as damaged / broken goods'}

    def clean_body(self):
        body = self.cleaned_data['body'].strip()
        if not body:
            raise forms.ValidationError('Comment cannot be empty.')
        return body


class ContainerPalletForm(forms.Form):
    """Build a pallet from a single container manifest line."""
    quantity = forms.IntegerField(min_value=1, label='Quantity on this pallet')
    expiry_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}),
                                  label='Expiry date (optional)')
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, container_item=None, **kwargs):
        self.container_item = container_item
        super().__init__(*args, **kwargs)
        if container_item is not None:
            remaining = container_item.remaining_quantity
            self.fields['quantity'].max_value = remaining
            self.fields['quantity'].widget.attrs.update({'max': remaining, 'min': 1})
            self.fields['quantity'].help_text = f'{remaining} of {container_item.quantity} still to palletize.'

    def clean_quantity(self):
        qty = self.cleaned_data['quantity']
        if self.container_item is not None and qty > self.container_item.remaining_quantity:
            raise forms.ValidationError(
                f'Only {self.container_item.remaining_quantity} left to palletize on this line.')
        return qty
