#!/usr/bin/env python
'''
glider_qc/glider_qc.py
'''
import numpy as np
import quantities as pq
from netCDF4 import num2date
from ioos_qartod.qc_tests import qc


class GliderQC(object):
    def __init__(self, ncfile):
        self.ncfile = ncfile

    def find_geophysical_variables(self):
        '''
        Returns a list of variable names matching the geophysical variable's
        standard names for temperature, conductivity, density and salinity.
        '''
        variables = []
        valid_standard_names = [
            'sea_water_temperature',
            'sea_water_electrical_conductivity',
            'sea_water_density',
            'sea_water_pressure',
            'sea_water_practical_salinity'
        ]

        for standard_name in valid_standard_names:
            ncvar = self.ncfile.get_variables_by_attributes(standard_name=standard_name)
            if len(ncvar) == 1:
                variables.append(ncvar[0].name)
        return variables

    def find_ancillary_variables(self, ncvariable):
        '''
        Returns the valid ancillary variables associated with a particular
        variable.

        :param netCDF4.Variable ncvariable: Variable to get the ancillary
                                            variables for
        '''
        valid_variables = []
        ancillary_variables = getattr(ncvariable, 'ancillary_variables', '').split(' ')
        for varname in ancillary_variables:
            # Skip the standard GliderDAC
            if varname == '%s_qc' % ncvariable.name:
                continue
            if varname in self.ncfile.variables:
                valid_variables.append(varname)
        return valid_variables

    def append_ancillary_variable(self, parent, child):
        '''
        Links two variables through the ancillary_variables attribute

        :param netCDF.Variable parent: Parent Variable
        :param netCDF.Variable child: Status Flag Variable
        '''

        ancillary_variables = getattr(parent, 'ancillary_variables', '').split(' ')
        ancillary_variables.append(child.name)
        parent.ancillary_variables = ' '.join(ancillary_variables)

    def create_qc_variables(self, ncvariable):
        '''
        Returns a list of variable names for the newly created variables for QC flags
        '''
        name = ncvariable.name
        standard_name = ncvariable.standard_name
        dims = ncvariable.dimensions

        templates = {
            'flat_line': {
                'name': 'qartod_%(name)s_flat_line_flag',
                'long_name': 'QARTOD Flat Line Test for %(standard_name)s',
                'standard_name': '%(standard_name)s status_flag',
                'flag_values': np.array([1, 2, 3, 4, 9], dtype=np.int8),
                'flag_meanings': 'GOOD NOT_EVALUATED SUSPECT BAD MISSING',
                'references': 'http://gliders.ioos.us/static/pdf/Manual-for-QC-of-Glider-Data_05_09_16.pdf',
                'qartod_test': 'flat_line'
            },
            'gross_range': {
                'name': 'qartod_%(name)s_gross_range_flag',
                'long_name': 'QARTOD Gross Range Test for %(standard_name)s',
                'standard_name': '%(standard_name)s status_flag',
                'flag_values': np.array([1, 2, 3, 4, 9], dtype=np.int8),
                'flag_meanings': 'GOOD NOT_EVALUATED SUSPECT BAD MISSING',
                'references': 'http://gliders.ioos.us/static/pdf/Manual-for-QC-of-Glider-Data_05_09_16.pdf',
                'qartod_test': 'gross_range'
            },
            'rate_of_change': {
                'name': 'qartod_%(name)s_rate_of_change_flag',
                'long_name': 'QARTOD Rate of Change Test for %(standard_name)s',
                'standard_name': '%(standard_name)s status_flag',
                'flag_values': np.array([1, 2, 3, 4, 9], dtype=np.int8),
                'flag_meanings': 'GOOD NOT_EVALUATED SUSPECT BAD MISSING',
                'references': 'http://gliders.ioos.us/static/pdf/Manual-for-QC-of-Glider-Data_05_09_16.pdf',
                'qartod_test': 'rate_of_change'
            },
            'spike': {
                'name': 'qartod_%(name)s_spike_flag',
                'long_name': 'QARTOD Spike Test for %(standard_name)s',
                'standard_name': '%(standard_name)s status_flag',
                'flag_values': np.array([1, 2, 3, 4, 9], dtype=np.int8),
                'flag_meanings': 'GOOD NOT_EVALUATED SUSPECT BAD MISSING',
                'references': 'http://gliders.ioos.us/static/pdf/Manual-for-QC-of-Glider-Data_05_09_16.pdf',
                'qartod_test': 'spike'
            },
            'pressure': {
                'name': 'qartod_monotonic_pressure_flag',
                'long_name': 'QARTOD Pressure Test for %(standard_name)s',
                'standard_name': '%(standard_name)s status_flag',
                'flag_values': np.array([1, 2, 3, 4, 9], dtype=np.int8),
                'flag_meanings': 'GOOD NOT_EVALUATED SUSPECT BAD MISSING',
                'references': 'http://gliders.ioos.us/static/pdf/Manual-for-QC-of-Glider-Data_05_09_16.pdf',
                'qartod_test': 'pressure'
            }
        }

        qcvariables = []

        for tname, template in templates.items():
            if tname == 'pressure' and standard_name != 'sea_water_pressure':
                continue
            variable_name = template['name'] % {'name': name}
            ncvar = self.ncfile.createVariable(variable_name, np.int8, dims, fill_value=np.int8(9))
            ncvar.units = '1'
            ncvar.standard_name = template['standard_name'] % {'standard_name': standard_name}
            ncvar.long_name = template['long_name'] % {'standard_name': standard_name}
            ncvar.flag_values = template['flag_values']
            ncvar.flag_meanings = template['flag_meanings']
            ncvar.references = template['references']
            ncvar.qartod_test = template['qartod_test']
            qcvariables.append(variable_name)
            self.append_ancillary_variable(ncvariable, ncvar)

        return qcvariables

    def apply_qc(self, ncvariable):
        '''
        Applies QC to a qartod variable

        :param netCDF4.Variable ncvariable: A QARTOD Variable
        '''
        f32_eps = np.finfo(np.float32).eps
        configuration = {
            'sea_water_temperature': {
                'flat_line': {
                    'low_reps': 4,
                    'high_reps': 8,
                    'eps': f32_eps
                },
                'gross_range': {
                    'sensor_span': [-5, 45]
                },
                'rate_of_change': {
                    'thresh_val': 5. / pq.hour
                },
                'spike': {
                    'low_thresh': 5,
                    'high_thresh': 10
                }
            }
        }

        qc_tests = {
            'flat_line': qc.flat_line_check,
            'gross_range': qc.range_check,
            'rate_of_change': qc.rate_of_change_check,
            'spike': qc.spike_check
        }

        qartod_test = getattr(ncvariable, 'qartod_test')
        standard_name = getattr(ncvariable, 'standard_name').split(' ')[0]
        parent = self.ncfile.get_variables_by_attributes(standard_name=standard_name)[0]
        test_params = configuration[standard_name][qartod_test]

        if qartod_test in ('rate_of_change', 'pressure'):
            times = self.ncfile.variables['time'][:]
            dates = np.array(num2date(times, self.ncfile.variables['time'].units), dtype='datetime64[ms]')
            test_params['times'] = dates
        test_params['arr'] = parent[:]

        qc_flags = qc_tests[qartod_test](**test_params)
        ncvariable[:] = qc_flags
