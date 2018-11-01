import csv
import gzip
import os
import sys
import pydicom
import json
from Tkinter import *
import Tkinter, tkFileDialog
import re
import argparse
import shutil
import datetime
import subprocess

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
    def __init__(self, filename, type, write_loc, log):
        #print('Creating new Physio instance for {}'.format(filename))
        self.data = []
        self.start_time = 0
        self.sr = 0
        self.type = type
        self.write_loc = write_loc
        self.log = log
        self.corrupt = 0
        self.typestrings = {'resp' : 'RESP', 'puls' : 'PULS', 'trigger' : 'EXT'}
        if filename.split('.')[-1] == 'gz':
            with gzip.open(filename, 'rb') as infile:
                filestring = infile.read()
                self.parse_physio(filestring)
        else:
            with open(filename, 'rb') as infile:
                filestring = infile.read()
                self._parse_physio(filestring)

    def _parse_physio(self, filestring):
        #do the heavy lifting here
        d = filestring.split()
        sr_str = self.typestrings[self.type] + '_SAMPLES_PER_SECOND'
        if sr_str not in d:
            log.write('PHYSIO FILE MISSING SR TAG\n')
            self.corrupt = -2
            return
        else:
            self.sr = d[d.index(sr_str) + 2]
        if 'LogStartMDHTime:' not in d:
            log.write('PHYSIO FILE MISSING START TIMESTAMP\n')
            self.corrupt = -1
            return
        else:
            self.start_time = float(d[d.index('LogStartMDHTime:') + 1])
        d_start = d.index(self.typestrings[self.type] + '_SAMPLE_INTERVAL') + 2
        d_stop = d.index('FINISHED') - 1
        self.data = d[d_start:d_stop]

    def data(self):
        return self.data

    def get_start_time(self):
        if self.corrupt < 0:
            return self.corrupt
        else:
            return self.start_time

    #write tsv file with data items one per line
    def write_tsv(self, outname):
        #print('Writing TSV at {}'.format(os.path.join(self.write_loc, outname)))
        with open(os.path.join(self.write_loc, outname), 'wb') as csv_out:
            tsvwriter = csv.writer(csv_out, delimiter='\t')
            for x in self.data:
                #print('Printing {}, type {}'.format(x, type(x)))
                if len(x) > 1:
                    x = [float(x)]
                tsvwriter.writerow(x)
            csv_out.close()
        #gzip the newly-created TSV
        with open(os.path.join(self.write_loc, outname), 'rb') as f_in:
            with open(os.path.join(self.write_loc, outname) + '.gz', 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        #remove original
        os.remove(os.path.join(self.write_loc, outname))
        #solve double-underscore naming problem
        cmd = 'rename s/__/_/ *'
        process = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
        out,err = process.communicate()


    #write json with column name, sampling rate, and start time
    def write_json(self, outname, dcm_start):
        data_out = {'SamplingFrequency' : self.sr, 'StartTime' : (float(self.start_time)-float(dcm_start))/1000, 'Columns' : self.type}
        with open(os.path.join(self.write_loc, outname), 'wb') as fp:
            json.dump(data_out, fp)
            fp.close()
        #solve double-underscore naming problem
        cmd = 'rename s/__/_/ *'
        process = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
        out,err = process.communicate()

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

    def get_taskname(self, timestamp):
        if timestamp < 0:
            return ("ERROR", timestamp)
        #check DICOMs for starting timestamp matching given, return task name
        k = self.dcm_dict.keys()
        k.sort()
        if len(k) == 1:
            return (self.dcm_dict[k[0]], k[0])
        for dcm in range(1,len(k)):
            #print('Checking timestamp {} against {}'.format(k[dcm],timestamp))
            if k[dcm] >= timestamp and k[dcm-1] < timestamp:
                return (self.dcm_dict[k[dcm]], k[dcm])
            if dcm-1 == 0 and k[dcm-1] > timestamp:
                return (self.dcm_dict[k[dcm-1]], k[dcm-1])
        return ("ERROR", -3)

class PhysioLoad:

    def __init__(self, directory, dcm_load, write_loc, log):
        self.directory = directory
        self.dcm_load = dcm_load
        self.formatter = BIDS_Formatter()
        self.write_loc = write_loc
        self.log = log

    def run(self):
        p = os.listdir(self.directory)
        print "Converting physio...\t\t",
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
            self.log.write('Conversion target: {}\t'.format(e))
            phys = Physio(os.path.join(self.directory, e), type, self.write_loc, self.log)
            resp = dcm.get_taskname(phys.get_start_time())
            if resp[0] == "ERROR":
                print('ERROR RETRIEVING TASK NAME FROM DICOM - SKIPPING')
                if resp[1] == -3:
                    log.write('TIMESTAMP MISMATCH ERROR\n')
                continue
            name = resp[0]
            dcm_start = resp[1]
            tname = self.formatter.bidsify(name, type, 'tsv')
            jname = self.formatter.bidsify(name, type, 'json')
            log.write('MATCHED TO {}\t'.format(tname.split('.')[0]))
            phys.write_tsv(tname)
            phys.write_json(jname, dcm_start)
            log.write('CONVERTED FILES WRITTEN\n')
        print('\t\t\tDONE\n')

class BIDS_Formatter:

    def __init__(self):
        pass

    def bidsify(self, fname, type, extension):
        #given a task name, bidsify it and return it (plus requested extension)
        #sub-X_ses-X_task-X_run-X_recording-X_physio
        base = fname.split('/')[-1]
        sub = base[base.index('CSI'):base.index('CSI')+4]
        sess = base[base.index('Sess'):base.index('Sess')+7]
        run = ''
        if 'Run' in base:
            run = base[base.index('Run'):base.index('Run')+6]
        sub = 'sub-' + sub
        sess = 'ses-' + sess.split('-')[1].split('_')[0].zfill(2)
        if len(run) > 0:
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

    #parse args
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--dicom")
    parser.add_argument("-p", "--physio")
    parser.add_argument("-o", "--output")
    parser.add_argument("-l", "--log")
    args = parser.parse_args()

    #check that DICOM and physio dirs specified
    if not args.dicom:
        print('Error: you need to specify a DICOM directory.')
        sys.exit()
    if not args.physio:
        print('Error: you need to specify a Physio directory.')
        sys.exit()

    dcm_dir = args.dicom
    physio_dir = args.physio

    print('\n')
    print('------------------------------')
    print('---Physio -> BIDS converter---')
    print('------------------------------')
    print('--------Austin Marcus---------')
    print('--TarrLab @ CMU October 2018--')
    print('------------------------------')
    print('\n')
    print('Select directories:')

    #check for specified output directory; create if it doesn't exist, or default to physio folder
    write_loc = ''
    if not args.output:
        print('No output folder specified - will use physio directory')
        write_loc = physio_dir
    else:
        write_loc = args.output
        print('Using output folder {}'.format(os.path.join(os.getcwd(), write_loc)))
        if not os.path.exists(write_loc):
            os.mkdir(write_loc)

    logfile = os.path.join(os.getcwd(), 'logs', '{}_physio2bids_log.txt'.format(datetime.datetime.now()))
    if args.log:
        logfile = args.log
    else:
        if not os.path.exists(os.path.join(os.getcwd(), 'logs')):
            os.mkdir('logs')

    dcm = DicomLoad(dcm_dir)
    with open(logfile, 'ab') as log:
        log.write('PHYSIO2BIDS -- {}\n'.format(datetime.datetime.now()))
        log.write('-------------------------------------------------\n')
        log.write('DICOM directory: {}\t'.format(dcm_dir))
        log.write('Physio directory: {}\t'.format(physio_dir))
        log.write('Output directory: {}\n'.format(write_loc))
        log.write('-------------------------------------------------\n')
        phys = PhysioLoad(physio_dir, dcm, write_loc, log)
        phys.run()
        log.write('-------------------------------------------------\n')
