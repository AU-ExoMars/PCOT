##
# Portions of the code below are modified from spectralpython,
# Copyright (C) 2002 Thomas Boggs; license follows:

# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions: 

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software. 

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE. 

from filters import Filter

def parseHeader(lines):
    dict = {}
    have_nonlowercase_param = False
    try:
        while lines:
            line = lines.pop(0)
            if line.find('=') == -1: continue
            if line[0] == ';': continue

            (key, sep, val) = line.partition('=')
            key = key.strip()
            if not key.islower():
                have_nonlowercase_param = True
                key = key.lower()
            val = val.strip()
            if val and val[0] == '{':
                str = val.strip()
                while str[-1] != '}':
                    line = lines.pop(0)
                    if line[0] == ';': continue

                    str += '\n' + line.strip()
                if key == 'description':
                    dict[key] = str.strip('{}').strip()
                else:
                    vals = str[1:-1].split(',')
                    for j in range(len(vals)):
                        vals[j] = vals[j].strip()
                    dict[key] = vals
            else:
                dict[key] = val

        if have_nonlowercase_param:
            ui.warn('Parameters with non-lowercase names encountered '\
                    'and converted to lowercase.')
        return dict
    except:
        raise Exception('ENVI parsing error')


class ENVIHeader:
    def __init__(self, f):
        try:
            isENVI = f.readline().strip().startswith('ENVI')
        except UnicodeDecodeError:
            f.close()
            raise Exception('File is not an ENVI header (is binary file?)')
        else:
            if not isENVI:
                f.close()
                raise Exception('File is not an ENVI file (no "ENVI" on first line)')
        
        lines = f.readlines()
        f.close()
        dict = parseHeader(lines)
        
        # get the important data out into fields
        
        # some odd nomeclature I will accept, but calling "width" and
        # "height" by these names seems needlessly obtuse.
        
        self.w = int(dict['samples'])
        self.h = int(dict['lines'])
        self.bands = int(dict['bands'])
                
        self.headerOffset = [int(dict['headerOffset']) if 'headerOffset' in dict else 0]
        self.littleEndian = dict['byte order']=='0'
        if dict['interleave'] != 'bsq':
            raise Exception("Only BSQ interleave is supported")
        if dict['data type'] != '4':
            raise Exception("Data type must be 32-bit float")
            
        if 'default bands' in dict:
            self.defaultBands = [int(x) for x in dict['default bands']]
        else:
            self.defaultBands = [0,1,2]
        
        if 'band names' in dict:
            bandNames = dict['band names']
        else:
            bandNames = [str(x) for x in range(self.bands)]

        if 'wavelength' in dict:
            wavelengths = [float(x) for x in dict['wavelength']]
            if 'fwhm' in dict:
                fwhm = [float(x) for x in dict['fwhm']]
            else:
                fwhm = [0 for _ in wavelengths]

            if 'data gain values' in dict:
                gain = [float(x) for x in dict['data gain values']]
            else:
                gain = [0 for _ in wavelengths]
                
            filters=[]
            for w,f,g,n in zip(wavelengths,fwhm,gain,bandNames):
                filters.append(Filter(w,f,g,n,n))

        if 'data ignore value' in dict:
            self.ignoreValue = float(dict['data ignore value'])
        else:
            self.ignoreValue = None

                 
if __name__ == '__main__':
    with open('RStar_AUPE/AUPE_LWAC_P03T01.hdr') as f:
        d = ENVIHeader(f)
