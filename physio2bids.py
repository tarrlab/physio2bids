import csv
import os
import sys
import pydicom
import json
from Tkinter import *
import Tkinter, tkFileDialog
import re

#Author - Austin Marcus
#TarrLab @ CMU October 2018

'''
Load in DICOMs from given folder
For folder of physio data:
    Per file:
        Create Physio object (read in, get data & info fields)
        Look up timestamp, cross-ref with DICOMs to find task name
        Write out physio to TSV [in BIDS format] in same location
'''

class Util:

    def __init__(self):
        pass

    def ts2ms(self, timestring):
        hh = float(timestring[0:2])
        mm = float(timestring[2:4])
        ss = float(timestring[4:6])
        ms = float(timestring[7:10])
        return self.hh2ms(hh) + self.mm2ms(mm) + self.ss2ms(ss) + ms

    def hh2ms(self, hh):
        return hh*60*60*1000

    def mm2ms(self, mm):
        return mm*60*1000

    def ss2ms(self, ss):
        return ss*1000


class Physio:

    #container for fields in one physio file
    def __init__(self, filename, type, write_loc):
        print('Creating new Physio instance for {}'.format(filename))
        self.data = []
        self.start_time = 0
        self.sr = 0
        self.type = type
        self.write_loc = write_loc
        self.typestrings = {'resp' : 'RESP', 'puls' : 'PULS', 'trigger' : 'EXT'}
        with open(filename, 'rb') as infile:
            filestring = infile.read()
            self._parse_physio(filestring)

    def _parse_physio(self, filestring):
        #do the heavy lifting here
        d = filestring.split()
        sr_str = self.typestrings[self.type] + '_SAMPLES_PER_SECOND'
        self.sr = d[d.index(sr_str) + 2]
        self.start_time = float(d[d.index('LogStartMDHTime:') + 1])
        d_start = d.index(self.typestrings[self.type] + '_SAMPLE_INTERVAL') + 2
        d_stop = d.index('FINISHED') - 1
        self.data = d[d_start:d_stop]

    def data(self):
        return self.data

    def get_start_time(self):
        return self.start_time

    #write tsv file with data items one per line
    def write_tsv(self, outname):
        with open(os.path.join(self.write_loc, outname), 'wb') as csv_out:
            tsvwriter = csv.writer(csv_out, delimiter='\t')
            for x in self.data:
                #print('Printing {}, type {}'.format(x, type(x)))
                if len(x) > 1:
                    x = [float(x)]
                tsvwriter.writerow(x)
            csv_out.close()

    #write json with column name, sampling rate, and start time
    def write_json(self, outname, dcm_start):
        data_out = {'SamplingFrequency' : self.sr, 'StartTime' : (float(self.start_time)-float(dcm_start))/1000, 'Columns' : self.type}
        with open(os.path.join(self.write_loc, outname), 'wb') as fp:
            json.dump(data_out, fp)
            fp.close()

class DicomLoad:

    #GIVE FULL PATH
    def __init__(self, directory):
        #load in all BOLD DICOMs from directory (just get first in folder)
        #get starting timestamp and name (ignore everything else), create dict
        print('Loading DICOMs from {}'.format(directory))
        d = [i for i in os.listdir(directory) if os.path.isdir(os.path.join(directory, i))]
        bold = [i for i in d if 'BOLD' in i]
        util = Util()
        self.dcm_dict = {}
        bold_count = 0
        for bd in bold:
            #cheap way to get first item
            f = [i for i in os.listdir(os.path.join(directory, bd)) if '000001.dcm' in i][0]
            ds = pydicom.dcmread(os.path.join(directory, bd, f))
            self.dcm_dict[util.ts2ms(ds.AcquisitionTime)] = bd
            bold_count += 1
        print('Loaded {} DICOMs'.format(bold_count))
        print('DEBUG::dicom timestamps:')
        k = self.dcm_dict.keys()
        k.sort()
        for key in k:
            print key


    def get_taskname(self, timestamp):
        #check DICOMs for starting timestamp matching given, return task name
        k = self.dcm_dict.keys()
        k.sort()
        if len(k) == 1:
            return (self.dcm_dict[k[0]], k[0])
        for dcm in range(1,len(k)):
            print('Checking timestamp {} against {}'.format(k[dcm],timestamp))
            if k[dcm] >= timestamp and k[dcm-1] < timestamp:
                return (self.dcm_dict[k[dcm]], k[dcm])
            if dcm-1 == 0 and k[dcm-1] > timestamp:
                return (self.dcm_dict[k[dcm-1]], k[dcm-1])
        return ("ERROR", 0)

class PhysioLoad:

    def __init__(self, directory, dcm_load, write_loc):
        self.directory = directory
        self.dcm_load = dcm_load
        self.formatter = BIDS_Formatter()
        self.write_loc = write_loc

    def run(self):
        p = os.listdir(self.directory)
        for e in p:
            type = ""
            if '.ext' in e:
                type = 'trigger'
            elif '.puls' in e:
                type = 'puls'
            elif '.resp' in e:
                type = 'resp'
            else:
                #not valid physio file - skip
                continue
            phys = Physio(os.path.join(self.directory, e), type, self.write_loc)
            resp = dcm.get_taskname(phys.get_start_time())
            if resp[0] == "ERROR":
                print('ERROR RETRIEVING TASK NAME FROM DICOM - EXITING')
                return
            name = resp[0]
            dcm_start = resp[1]
            tname = self.formatter.bidsify(name, type, 'tsv')
            jname = self.formatter.bidsify(name, type, 'json')
            phys.write_tsv(os.path.join(self.directory, tname))
            phys.write_json(os.path.join(self.directory, jname), dcm_start)

class BIDS_Formatter:

    def __init__(self):
        pass

    def bidsify(self, fname, type, extension):
        #given a task name, bidsify it and return it (plus requested extension)
        #sub-X_ses-X_task-X_run-X_recording-X_physio
        base = fname.split('/')[-1]
        sub = base[base.index('CSI'):base.index('CSI')+4]
        sess = base[base.index('Sess'):base.index('Sess')+7]
        run = base[base.index('Run'):base.index('Run')+6]
        sub = 'sub-' + sub
        sess = 'ses-' + sess.split('-')[1].split('_')[0].zfill(2)
        run = 'run-' + run.split('-')[1].split('_')[0].zfill(2)
        task = ''
        if 'SceneLocal' in base:
            task = 'task-localizer'
        else:
            task = 'task-5000scenes'
        rec = ''
        if 'puls' in type:
            rec = 'recording-cardiac'
        elif 'resp' in type:
            rec = 'recording-respiratory'
        elif 'trigger' in type:
            rec = 'recording-trigger'
        s = '_'
        return s.join([sub, sess, task, run, rec]) + '_physio.' + extension

if __name__== "__main__":

    print('\n')
    print('------------------------------')
    print('---Physio -> BIDS converter---')
    print('------------------------------')
    print('--------Austin Marcus---------')
    print('--TarrLab @ CMU October 2018--')
    print('------------------------------')
    print('\n')
    print('Select directories:')

    dcm_dir = ''
    physio_dir = ''

    dcm_dir = tkFileDialog.askdirectory(title='Select DICOM directory')
    physio_dir = tkFileDialog.askdirectory(title='Select Physio directory')

    #check for specified output directory; create if it doesn't exist, or default to physio folder
    write_loc = ''
    if len(sys.argv[1]) == 0:
        write_loc = physio_dir
    else:
        write_loc = sys.argv[1]
        if not os.path.exists(write_loc):
            os.mkdir(write_loc)

    dcm = DicomLoad(dcm_dir)
    phys = PhysioLoad(physio_dir, dcm, write_loc)
    phys.run()

