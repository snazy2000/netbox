from django import forms
from django.db.models import Count

from dcim.models import Site, Rack, Device, Interface
from extras.forms import CustomFieldForm, CustomFieldBulkEditForm, CustomFieldFilterForm
from tenancy.models import Tenant
from utilities.forms import (
    APISelect, BootstrapMixin, BulkEditNullBooleanSelect, BulkImportForm, CSVDataField, ExpandableIPAddressField,
    FilterChoiceField, Livesearch, ReturnURLForm, SlugField, add_blank_choice,
)

from .models import (
    Aggregate, IPAddress, IPADDRESS_STATUS_CHOICES, Prefix, PREFIX_STATUS_CHOICES, RIR, Role, Service, VLAN,
    VLANGroup, VLAN_STATUS_CHOICES, VRF,
)


IP_FAMILY_CHOICES = [
    ('', 'All'),
    (4, 'IPv4'),
    (6, 'IPv6'),
]

PREFIX_MASK_LENGTH_CHOICES = [
    ('', '---------'),
] + [(i, i) for i in range(1, 128)]

IPADDRESS_MASK_LENGTH_CHOICES = PREFIX_MASK_LENGTH_CHOICES + [(128, 128)]


#
# VRFs
#

class VRFForm(BootstrapMixin, CustomFieldForm):

    class Meta:
        model = VRF
        fields = ['name', 'rd', 'tenant', 'enforce_unique', 'description']
        labels = {
            'rd': "RD",
        }
        help_texts = {
            'rd': "Route distinguisher in any format",
        }


class VRFFromCSVForm(forms.ModelForm):
    tenant = forms.ModelChoiceField(Tenant.objects.all(), to_field_name='name', required=False,
                                    error_messages={'invalid_choice': 'Tenant not found.'})

    class Meta:
        model = VRF
        fields = ['name', 'rd', 'tenant', 'enforce_unique', 'description']


class VRFImportForm(BootstrapMixin, BulkImportForm):
    csv = CSVDataField(csv_form=VRFFromCSVForm)


class VRFBulkEditForm(BootstrapMixin, CustomFieldBulkEditForm):
    pk = forms.ModelMultipleChoiceField(queryset=VRF.objects.all(), widget=forms.MultipleHiddenInput)
    tenant = forms.ModelChoiceField(queryset=Tenant.objects.all(), required=False)
    enforce_unique = forms.NullBooleanField(
        required=False, widget=BulkEditNullBooleanSelect, label='Enforce unique space'
    )
    description = forms.CharField(max_length=100, required=False)

    class Meta:
        nullable_fields = ['tenant', 'description']


class VRFFilterForm(BootstrapMixin, CustomFieldFilterForm):
    model = VRF
    q = forms.CharField(required=False, label='Search')
    tenant = FilterChoiceField(queryset=Tenant.objects.annotate(filter_count=Count('vrfs')), to_field_name='slug',
                               null_option=(0, None))


#
# RIRs
#

class RIRForm(BootstrapMixin, forms.ModelForm):
    slug = SlugField()

    class Meta:
        model = RIR
        fields = ['name', 'slug', 'is_private']


class RIRFilterForm(BootstrapMixin, forms.Form):
    is_private = forms.NullBooleanField(required=False, label='Private', widget=forms.Select(choices=[
        ('', '---------'),
        ('True', 'Yes'),
        ('False', 'No'),
    ]))


#
# Aggregates
#

class AggregateForm(BootstrapMixin, CustomFieldForm):

    class Meta:
        model = Aggregate
        fields = ['prefix', 'rir', 'date_added', 'description']
        help_texts = {
            'prefix': "IPv4 or IPv6 network",
            'rir': "Regional Internet Registry responsible for this prefix",
            'date_added': "Format: YYYY-MM-DD",
        }


class AggregateFromCSVForm(forms.ModelForm):
    rir = forms.ModelChoiceField(queryset=RIR.objects.all(), to_field_name='name',
                                 error_messages={'invalid_choice': 'RIR not found.'})

    class Meta:
        model = Aggregate
        fields = ['prefix', 'rir', 'date_added', 'description']


class AggregateImportForm(BootstrapMixin, BulkImportForm):
    csv = CSVDataField(csv_form=AggregateFromCSVForm)


class AggregateBulkEditForm(BootstrapMixin, CustomFieldBulkEditForm):
    pk = forms.ModelMultipleChoiceField(queryset=Aggregate.objects.all(), widget=forms.MultipleHiddenInput)
    rir = forms.ModelChoiceField(queryset=RIR.objects.all(), required=False, label='RIR')
    date_added = forms.DateField(required=False)
    description = forms.CharField(max_length=100, required=False)

    class Meta:
        nullable_fields = ['date_added', 'description']


class AggregateFilterForm(BootstrapMixin, CustomFieldFilterForm):
    model = Aggregate
    q = forms.CharField(required=False, label='Search')
    family = forms.ChoiceField(required=False, choices=IP_FAMILY_CHOICES, label='Address Family')
    rir = FilterChoiceField(
        queryset=RIR.objects.annotate(filter_count=Count('aggregates')),
        to_field_name='slug',
        label='RIR'
    )


#
# Roles
#

class RoleForm(BootstrapMixin, forms.ModelForm):
    slug = SlugField()

    class Meta:
        model = Role
        fields = ['name', 'slug']


#
# Prefixes
#

class PrefixForm(BootstrapMixin, CustomFieldForm):
    site = forms.ModelChoiceField(queryset=Site.objects.all(), required=False, label='Site',
                                  widget=forms.Select(attrs={'filter-for': 'vlan', 'nullable': 'true'}))
    vlan = forms.ModelChoiceField(queryset=VLAN.objects.all(), required=False, label='VLAN',
                                  widget=APISelect(api_url='/api/ipam/vlans/?site_id={{site}}',
                                                   display_field='display_name'))

    class Meta:
        model = Prefix
        fields = ['prefix', 'vrf', 'tenant', 'site', 'vlan', 'status', 'role', 'is_pool', 'description']

    def __init__(self, *args, **kwargs):
        super(PrefixForm, self).__init__(*args, **kwargs)

        self.fields['vrf'].empty_label = 'Global'

        # Initialize field without choices to avoid pulling all VLANs from the database
        if self.is_bound and self.data.get('site'):
            self.fields['vlan'].queryset = VLAN.objects.filter(site__pk=self.data['site'])
        elif self.initial.get('site'):
            self.fields['vlan'].queryset = VLAN.objects.filter(site=self.initial['site'])
        else:
            self.fields['vlan'].queryset = VLAN.objects.filter(site=None)


class PrefixFromCSVForm(forms.ModelForm):
    vrf = forms.ModelChoiceField(queryset=VRF.objects.all(), required=False, to_field_name='rd',
                                 error_messages={'invalid_choice': 'VRF not found.'})
    tenant = forms.ModelChoiceField(Tenant.objects.all(), to_field_name='name', required=False,
                                    error_messages={'invalid_choice': 'Tenant not found.'})
    site = forms.ModelChoiceField(queryset=Site.objects.all(), required=False, to_field_name='name',
                                  error_messages={'invalid_choice': 'Site not found.'})
    vlan_group_name = forms.CharField(required=False)
    vlan_vid = forms.IntegerField(required=False)
    status_name = forms.ChoiceField(choices=[(s[1], s[0]) for s in PREFIX_STATUS_CHOICES])
    role = forms.ModelChoiceField(queryset=Role.objects.all(), required=False, to_field_name='name',
                                  error_messages={'invalid_choice': 'Invalid role.'})

    class Meta:
        model = Prefix
        fields = ['prefix', 'vrf', 'tenant', 'site', 'vlan_group_name', 'vlan_vid', 'status_name', 'role', 'is_pool',
                  'description']

    def clean(self):

        super(PrefixFromCSVForm, self).clean()

        site = self.cleaned_data.get('site')
        vlan_group_name = self.cleaned_data.get('vlan_group_name')
        vlan_vid = self.cleaned_data.get('vlan_vid')
        vlan_group = None
        vlan = None

        # Validate VLAN group
        if vlan_group_name:
            try:
                vlan_group = VLANGroup.objects.get(site=site, name=vlan_group_name)
            except VLANGroup.DoesNotExist:
                if site:
                    self.add_error('vlan_group_name', "Invalid VLAN group ({} - {}).".format(site, vlan_group_name))
                else:
                    self.add_error('vlan_group_name', "Invalid global VLAN group ({}).".format(vlan_group_name))

        # Validate VLAN
        if vlan_vid:
            try:
                self.instance.vlan = VLAN.objects.get(site=site, group=vlan_group, vid=vlan_vid)
            except VLAN.DoesNotExist:
                if site:
                    self.add_error('vlan_vid', "Invalid VLAN ID ({}) for site {}.".format(vlan_vid, site))
                elif vlan_group:
                    self.add_error('vlan_vid', "Invalid VLAN ID ({}) for group {}.".format(vlan_vid, vlan_group_name))
                elif not vlan_group_name:
                    self.add_error('vlan_vid', "Invalid global VLAN ID ({}).".format(vlan_vid))
            except VLAN.MultipleObjectsReturned:
                self.add_error('vlan_vid', "Multiple VLANs found ({} - VID {})".format(site, vlan_vid))

    def save(self, *args, **kwargs):

        # Assign Prefix status by name
        self.instance.status = dict(self.fields['status_name'].choices)[self.cleaned_data['status_name']]

        return super(PrefixFromCSVForm, self).save(*args, **kwargs)


class PrefixImportForm(BootstrapMixin, BulkImportForm):
    csv = CSVDataField(csv_form=PrefixFromCSVForm)


class PrefixBulkEditForm(BootstrapMixin, CustomFieldBulkEditForm):
    pk = forms.ModelMultipleChoiceField(queryset=Prefix.objects.all(), widget=forms.MultipleHiddenInput)
    site = forms.ModelChoiceField(queryset=Site.objects.all(), required=False)
    vrf = forms.ModelChoiceField(queryset=VRF.objects.all(), required=False, label='VRF')
    tenant = forms.ModelChoiceField(queryset=Tenant.objects.all(), required=False)
    status = forms.ChoiceField(choices=add_blank_choice(PREFIX_STATUS_CHOICES), required=False)
    role = forms.ModelChoiceField(queryset=Role.objects.all(), required=False)
    is_pool = forms.NullBooleanField(required=False, widget=BulkEditNullBooleanSelect, label='Is a pool')
    description = forms.CharField(max_length=100, required=False)

    class Meta:
        nullable_fields = ['site', 'vrf', 'tenant', 'role', 'description']


def prefix_status_choices():
    status_counts = {}
    for status in Prefix.objects.values('status').annotate(count=Count('status')).order_by('status'):
        status_counts[status['status']] = status['count']
    return [(s[0], u'{} ({})'.format(s[1], status_counts.get(s[0], 0))) for s in PREFIX_STATUS_CHOICES]


class PrefixFilterForm(BootstrapMixin, CustomFieldFilterForm):
    model = Prefix
    q = forms.CharField(required=False, label='Search')
    parent = forms.CharField(required=False, label='Parent prefix', widget=forms.TextInput(attrs={
        'placeholder': 'Prefix',
    }))
    family = forms.ChoiceField(required=False, choices=IP_FAMILY_CHOICES, label='Address family')
    mask_length = forms.ChoiceField(required=False, choices=PREFIX_MASK_LENGTH_CHOICES, label='Mask length')
    vrf = FilterChoiceField(
        queryset=VRF.objects.annotate(filter_count=Count('prefixes')),
        to_field_name='rd',
        label='VRF',
        null_option=(0, 'Global')
    )
    tenant = FilterChoiceField(
        queryset=Tenant.objects.annotate(filter_count=Count('prefixes')),
        to_field_name='slug',
        null_option=(0, 'None')
    )
    status = forms.MultipleChoiceField(choices=prefix_status_choices, required=False)
    site = FilterChoiceField(
        queryset=Site.objects.annotate(filter_count=Count('prefixes')),
        to_field_name='slug',
        null_option=(0, 'None')
    )
    role = FilterChoiceField(
        queryset=Role.objects.annotate(filter_count=Count('prefixes')),
        to_field_name='slug',
        null_option=(0, 'None')
    )
    expand = forms.BooleanField(required=False, label='Expand prefix hierarchy')


#
# IP addresses
#

class IPAddressForm(BootstrapMixin, ReturnURLForm, CustomFieldForm):
    interface_site = forms.ModelChoiceField(
        queryset=Site.objects.all(), required=False, label='Site', widget=forms.Select(
            attrs={'filter-for': 'interface_rack'}
        )
    )
    interface_rack = forms.ModelChoiceField(
        queryset=Rack.objects.all(), required=False, label='Rack', widget=APISelect(
            api_url='/api/dcim/racks/?site_id={{interface_site}}', display_field='display_name',
            attrs={'filter-for': 'interface_device', 'nullable': 'true'}
        )
    )
    interface_device = forms.ModelChoiceField(
        queryset=Device.objects.all(), required=False, label='Device', widget=APISelect(
            api_url='/api/dcim/devices/?site_id={{interface_site}}&rack_id={{interface_rack}}',
            display_field='display_name', attrs={'filter-for': 'interface'}
        )
    )
    nat_site = forms.ModelChoiceField(
        queryset=Site.objects.all(), required=False, label='Site', widget=forms.Select(
            attrs={'filter-for': 'nat_device'}
        )
    )
    nat_device = forms.ModelChoiceField(
        queryset=Device.objects.all(), required=False, label='Device', widget=APISelect(
            api_url='/api/dcim/devices/?site_id={{nat_site}}', display_field='display_name',
            attrs={'filter-for': 'nat_inside'}
        )
    )
    livesearch = forms.CharField(
        required=False, label='IP Address', widget=Livesearch(
            query_key='q', query_url='ipam-api:ipaddress-list', field_to_update='nat_inside', obj_label='address'
        )
    )
    primary_for_device = forms.BooleanField(required=False, label='Make this the primary IP for the device')

    class Meta:
        model = IPAddress
        fields = ['address', 'vrf', 'tenant', 'status', 'description', 'interface', 'primary_for_device', 'nat_inside']
        widgets = {
            'interface': APISelect(api_url='/api/dcim/interfaces/?device_id={{interface_device}}'),
            'nat_inside': APISelect(api_url='/api/ipam/ip-addresses/?device_id={{nat_device}}', display_field='address')
        }

    def __init__(self, *args, **kwargs):
        super(IPAddressForm, self).__init__(*args, **kwargs)

        self.fields['vrf'].empty_label = 'Global'

        # If an interface has been assigned, initialize site, rack, and device
        if self.instance.interface:
            self.initial['interface_site'] = self.instance.interface.device.site
            self.initial['interface_rack'] = self.instance.interface.device.rack
            self.initial['interface_device'] = self.instance.interface.device

        # Limit rack choices
        if self.is_bound and self.data.get('interface_site'):
            self.fields['interface_rack'].queryset = Rack.objects.filter(site__pk=self.data['interface_site'])
        elif self.initial.get('interface_site'):
            self.fields['interface_rack'].queryset = Rack.objects.filter(site=self.initial['interface_site'])
        else:
            self.fields['interface_rack'].choices = []

        # Limit device choices
        if self.is_bound and self.data.get('interface_rack'):
            self.fields['interface_device'].queryset = Device.objects.filter(rack=self.data['interface_rack'])
        elif self.initial.get('interface_rack'):
            self.fields['interface_device'].queryset = Device.objects.filter(rack=self.initial['interface_rack'])
        else:
            self.fields['interface_device'].choices = []

        # Limit interface choices
        if self.is_bound and self.data.get('interface_device'):
            self.fields['interface'].queryset = Interface.objects.filter(device=self.data['interface_device'])
        elif self.initial.get('interface_device'):
            self.fields['interface'].queryset = Interface.objects.filter(device=self.initial['interface_device'])
        else:
            self.fields['interface'].choices = []

        # Initialize primary_for_device if IP address is already assigned
        if self.instance.interface is not None:
            device = self.instance.interface.device
            if (
                self.instance.address.version == 4 and device.primary_ip4 == self.instance or
                self.instance.address.version == 6 and device.primary_ip6 == self.instance
            ):
                self.initial['primary_for_device'] = True

        if self.instance.nat_inside:
            nat_inside = self.instance.nat_inside
            # If the IP is assigned to an interface, populate site/device fields accordingly
            if self.instance.nat_inside.interface:
                self.initial['nat_site'] = self.instance.nat_inside.interface.device.site.pk
                self.initial['nat_device'] = self.instance.nat_inside.interface.device.pk
                self.fields['nat_device'].queryset = Device.objects.filter(
                    site=nat_inside.interface.device.site
                )
                self.fields['nat_inside'].queryset = IPAddress.objects.filter(
                    interface__device=nat_inside.interface.device
                )
            else:
                self.fields['nat_inside'].queryset = IPAddress.objects.filter(pk=nat_inside.pk)
        else:
            # Initialize nat_device choices if nat_site is set
            if self.is_bound and self.data.get('nat_site'):
                self.fields['nat_device'].queryset = Device.objects.filter(site__pk=self.data['nat_site'])
            elif self.initial.get('nat_site'):
                self.fields['nat_device'].queryset = Device.objects.filter(site=self.initial['nat_site'])
            else:
                self.fields['nat_device'].choices = []
            # Initialize nat_inside choices if nat_device is set
            if self.is_bound and self.data.get('nat_device'):
                self.fields['nat_inside'].queryset = IPAddress.objects.filter(
                    interface__device__pk=self.data['nat_device'])
            elif self.initial.get('nat_device'):
                self.fields['nat_inside'].queryset = IPAddress.objects.filter(
                    interface__device__pk=self.initial['nat_device'])
            else:
                self.fields['nat_inside'].choices = []

    def clean(self):
        super(IPAddressForm, self).clean()

        # Primary IP assignment is only available if an interface has been assigned.
        if self.cleaned_data.get('primary_for_device') and not self.cleaned_data.get('interface'):
            self.add_error(
                'primary_for_device', "Only IP addresses assigned to an interface can be designated as primary IPs."
            )

    def save(self, *args, **kwargs):

        ipaddress = super(IPAddressForm, self).save(*args, **kwargs)

        # Assign this IPAddress as the primary for the associated Device.
        if self.cleaned_data['primary_for_device']:
            device = self.cleaned_data['interface'].device
            if ipaddress.address.version == 4:
                device.primary_ip4 = ipaddress
            else:
                device.primary_ip6 = ipaddress
            device.save()

        # Clear assignment as primary for device if set.
        else:
            try:
                if ipaddress.address.version == 4:
                    device = ipaddress.primary_ip4_for
                    device.primary_ip4 = None
                else:
                    device = ipaddress.primary_ip6_for
                    device.primary_ip6 = None
                device.save()
            except Device.DoesNotExist:
                pass

        return ipaddress


class IPAddressBulkAddForm(BootstrapMixin, CustomFieldForm):
    address_pattern = ExpandableIPAddressField(label='Address Pattern')
    vrf = forms.ModelChoiceField(queryset=VRF.objects.all(), required=False, label='VRF', empty_label='Global')

    pattern_map = ('address_pattern', 'address')

    class Meta:
        model = IPAddress
        fields = ['address_pattern', 'vrf', 'tenant', 'status', 'description']


class IPAddressFromCSVForm(forms.ModelForm):
    vrf = forms.ModelChoiceField(queryset=VRF.objects.all(), required=False, to_field_name='rd',
                                 error_messages={'invalid_choice': 'VRF not found.'})
    tenant = forms.ModelChoiceField(Tenant.objects.all(), to_field_name='name', required=False,
                                    error_messages={'invalid_choice': 'Tenant not found.'})
    status_name = forms.ChoiceField(choices=[(s[1], s[0]) for s in IPADDRESS_STATUS_CHOICES])
    device = forms.ModelChoiceField(queryset=Device.objects.all(), required=False, to_field_name='name',
                                    error_messages={'invalid_choice': 'Device not found.'})
    interface_name = forms.CharField(required=False)
    is_primary = forms.BooleanField(required=False)

    class Meta:
        model = IPAddress
        fields = ['address', 'vrf', 'tenant', 'status_name', 'device', 'interface_name', 'is_primary', 'description']

    def clean(self):

        device = self.cleaned_data.get('device')
        interface_name = self.cleaned_data.get('interface_name')
        is_primary = self.cleaned_data.get('is_primary')

        # Validate interface
        if device and interface_name:
            try:
                Interface.objects.get(device=device, name=interface_name)
            except Interface.DoesNotExist:
                self.add_error('interface_name', "Invalid interface ({}) for {}".format(interface_name, device))
        elif device and not interface_name:
            self.add_error('interface_name', "Device set ({}) but interface missing".format(device))
        elif interface_name and not device:
            self.add_error('device', "Interface set ({}) but device missing or invalid".format(interface_name))

        # Validate is_primary
        if is_primary and not device:
            self.add_error('is_primary', "No device specified; cannot set as primary IP")

    def save(self, *args, **kwargs):

        # Assign status by name
        self.instance.status = dict(self.fields['status_name'].choices)[self.cleaned_data['status_name']]

        # Set interface
        if self.cleaned_data['device'] and self.cleaned_data['interface_name']:
            self.instance.interface = Interface.objects.get(device=self.cleaned_data['device'],
                                                            name=self.cleaned_data['interface_name'])
        # Set as primary for device
        if self.cleaned_data['is_primary']:
            if self.instance.address.version == 4:
                self.instance.primary_ip4_for = self.cleaned_data['device']
            elif self.instance.address.version == 6:
                self.instance.primary_ip6_for = self.cleaned_data['device']

        return super(IPAddressFromCSVForm, self).save(*args, **kwargs)


class IPAddressImportForm(BootstrapMixin, BulkImportForm):
    csv = CSVDataField(csv_form=IPAddressFromCSVForm)


class IPAddressBulkEditForm(BootstrapMixin, CustomFieldBulkEditForm):
    pk = forms.ModelMultipleChoiceField(queryset=IPAddress.objects.all(), widget=forms.MultipleHiddenInput)
    vrf = forms.ModelChoiceField(queryset=VRF.objects.all(), required=False, label='VRF')
    tenant = forms.ModelChoiceField(queryset=Tenant.objects.all(), required=False)
    status = forms.ChoiceField(choices=add_blank_choice(IPADDRESS_STATUS_CHOICES), required=False)
    description = forms.CharField(max_length=100, required=False)

    class Meta:
        nullable_fields = ['vrf', 'tenant', 'description']


def ipaddress_status_choices():
    status_counts = {}
    for status in IPAddress.objects.values('status').annotate(count=Count('status')).order_by('status'):
        status_counts[status['status']] = status['count']
    return [(s[0], u'{} ({})'.format(s[1], status_counts.get(s[0], 0))) for s in IPADDRESS_STATUS_CHOICES]


class IPAddressFilterForm(BootstrapMixin, CustomFieldFilterForm):
    model = IPAddress
    q = forms.CharField(required=False, label='Search')
    parent = forms.CharField(required=False, label='Parent Prefix', widget=forms.TextInput(attrs={
        'placeholder': 'Prefix',
    }))
    family = forms.ChoiceField(required=False, choices=IP_FAMILY_CHOICES, label='Address family')
    mask_length = forms.ChoiceField(required=False, choices=IPADDRESS_MASK_LENGTH_CHOICES, label='Mask length')
    vrf = FilterChoiceField(
        queryset=VRF.objects.annotate(filter_count=Count('ip_addresses')),
        to_field_name='rd',
        label='VRF',
        null_option=(0, 'Global')
    )
    tenant = FilterChoiceField(
        queryset=Tenant.objects.annotate(filter_count=Count('ip_addresses')),
        to_field_name='slug',
        null_option=(0, 'None')
    )
    status = forms.MultipleChoiceField(choices=ipaddress_status_choices, required=False)


#
# VLAN groups
#

class VLANGroupForm(BootstrapMixin, forms.ModelForm):
    slug = SlugField()

    class Meta:
        model = VLANGroup
        fields = ['site', 'name', 'slug']


class VLANGroupFilterForm(BootstrapMixin, forms.Form):
    site = FilterChoiceField(
        queryset=Site.objects.annotate(filter_count=Count('vlan_groups')),
        to_field_name='slug',
        null_option=(0, 'Global')
    )


#
# VLANs
#

class VLANForm(BootstrapMixin, CustomFieldForm):
    group = forms.ModelChoiceField(queryset=VLANGroup.objects.all(), required=False, label='Group', widget=APISelect(
        api_url='/api/ipam/vlan-groups/?site_id={{site}}',
    ))

    class Meta:
        model = VLAN
        fields = ['site', 'group', 'vid', 'name', 'tenant', 'status', 'role', 'description']
        help_texts = {
            'site': "Leave blank if this VLAN spans multiple sites",
            'group': "VLAN group (optional)",
            'vid': "Configured VLAN ID",
            'name': "Configured VLAN name",
            'status': "Operational status of this VLAN",
            'role': "The primary function of this VLAN",
        }
        widgets = {
            'site': forms.Select(attrs={'filter-for': 'group', 'nullable': 'true'}),
        }

    def __init__(self, *args, **kwargs):

        super(VLANForm, self).__init__(*args, **kwargs)

        # Limit VLAN group choices
        if self.is_bound and self.data.get('site'):
            self.fields['group'].queryset = VLANGroup.objects.filter(site__pk=self.data['site'])
        elif self.initial.get('site'):
            self.fields['group'].queryset = VLANGroup.objects.filter(site=self.initial['site'])
        else:
            self.fields['group'].queryset = VLANGroup.objects.filter(site=None)


class VLANFromCSVForm(forms.ModelForm):
    site = forms.ModelChoiceField(
        queryset=Site.objects.all(), required=False, to_field_name='name',
        error_messages={'invalid_choice': 'Site not found.'}
    )
    group_name = forms.CharField(required=False)
    tenant = forms.ModelChoiceField(
        Tenant.objects.all(), to_field_name='name', required=False,
        error_messages={'invalid_choice': 'Tenant not found.'}
    )
    status_name = forms.ChoiceField(choices=[(s[1], s[0]) for s in VLAN_STATUS_CHOICES])
    role = forms.ModelChoiceField(
        queryset=Role.objects.all(), required=False, to_field_name='name',
        error_messages={'invalid_choice': 'Invalid role.'}
    )

    class Meta:
        model = VLAN
        fields = ['site', 'group_name', 'vid', 'name', 'tenant', 'status_name', 'role', 'description']

    def clean(self):

        super(VLANFromCSVForm, self).clean()

        # Validate VLANGroup
        group_name = self.cleaned_data.get('group_name')
        if group_name:
            try:
                vlan_group = VLANGroup.objects.get(site=self.cleaned_data.get('site'), name=group_name)
            except VLANGroup.DoesNotExist:
                self.add_error('group_name', "Invalid VLAN group {}.".format(group_name))

    def save(self, *args, **kwargs):

        vlan = super(VLANFromCSVForm, self).save(commit=False)

        # Assign VLANGroup by site and name
        if self.cleaned_data['group_name']:
            vlan.group = VLANGroup.objects.get(site=self.cleaned_data['site'], name=self.cleaned_data['group_name'])

        # Assign VLAN status by name
        vlan.status = dict(self.fields['status_name'].choices)[self.cleaned_data['status_name']]

        if kwargs.get('commit'):
            vlan.save()
        return vlan


class VLANImportForm(BootstrapMixin, BulkImportForm):
    csv = CSVDataField(csv_form=VLANFromCSVForm)


class VLANBulkEditForm(BootstrapMixin, CustomFieldBulkEditForm):
    pk = forms.ModelMultipleChoiceField(queryset=VLAN.objects.all(), widget=forms.MultipleHiddenInput)
    site = forms.ModelChoiceField(queryset=Site.objects.all(), required=False)
    group = forms.ModelChoiceField(queryset=VLANGroup.objects.all(), required=False)
    tenant = forms.ModelChoiceField(queryset=Tenant.objects.all(), required=False)
    status = forms.ChoiceField(choices=add_blank_choice(VLAN_STATUS_CHOICES), required=False)
    role = forms.ModelChoiceField(queryset=Role.objects.all(), required=False)
    description = forms.CharField(max_length=100, required=False)

    class Meta:
        nullable_fields = ['group', 'tenant', 'role', 'description']


def vlan_status_choices():
    status_counts = {}
    for status in VLAN.objects.values('status').annotate(count=Count('status')).order_by('status'):
        status_counts[status['status']] = status['count']
    return [(s[0], u'{} ({})'.format(s[1], status_counts.get(s[0], 0))) for s in VLAN_STATUS_CHOICES]


class VLANFilterForm(BootstrapMixin, CustomFieldFilterForm):
    model = VLAN
    q = forms.CharField(required=False, label='Search')
    site = FilterChoiceField(
        queryset=Site.objects.annotate(filter_count=Count('vlans')),
        to_field_name='slug',
        null_option=(0, 'Global')
    )
    group_id = FilterChoiceField(
        queryset=VLANGroup.objects.annotate(filter_count=Count('vlans')),
        label='VLAN group',
        null_option=(0, 'None')
    )
    tenant = FilterChoiceField(
        queryset=Tenant.objects.annotate(filter_count=Count('vlans')),
        to_field_name='slug',
        null_option=(0, 'None')
    )
    status = forms.MultipleChoiceField(choices=vlan_status_choices, required=False)
    role = FilterChoiceField(
        queryset=Role.objects.annotate(filter_count=Count('vlans')),
        to_field_name='slug',
        null_option=(0, 'None')
    )


#
# Services
#

class ServiceForm(BootstrapMixin, forms.ModelForm):

    class Meta:
        model = Service
        fields = ['name', 'protocol', 'port', 'ipaddresses', 'description']
        help_texts = {
            'ipaddresses': "IP address assignment is optional. If no IPs are selected, the service is assumed to be "
                           "reachable via all IPs assigned to the device.",
        }

    def __init__(self, *args, **kwargs):

        super(ServiceForm, self).__init__(*args, **kwargs)

        # Limit IP address choices to those assigned to interfaces of the parent device
        self.fields['ipaddresses'].queryset = IPAddress.objects.filter(interface__device=self.instance.device)
