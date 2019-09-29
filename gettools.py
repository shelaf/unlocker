#!/usr/bin/env python
"""
The MIT License (MIT)

Copyright (c) 2015-2017 Dave Parsons

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the 'Software'), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

from __future__ import division, print_function

import os
import shutil
import sys
import tarfile
import time
import zipfile
from contextlib import closing

try:
    # For Python 3.0 and later
    # noinspection PyCompatibility
    from urllib.request import urlopen, urlretrieve
    # noinspection PyCompatibility
    from html.parser import HTMLParser
except ImportError:
    # Fall back to Python 2
    # noinspection PyCompatibility
    from urllib2 import urlopen
    # noinspection PyCompatibility
    from HTMLParser import HTMLParser
    # noinspection PyCompatibility
    from urllib import urlretrieve


# Parse the Fusion directory page
class CDSParser(HTMLParser):

    def __init__(self):
        HTMLParser.__init__(self)
        self.reset()
        self.HTMLDATA = []

    def handle_data(self, data):
        # Build a list of numeric data from any element
        if data.find("\n") == -1:
            if data[0].isdigit():
                self.HTMLDATA.append(data)
                self.HTMLDATA.sort(key=lambda s: [int(u) for u in s.split('.')])

    def clean(self):
        self.HTMLDATA = []


def convertpath(path):
    # OS path separator replacement funciton
    return path.replace(os.path.sep, '/')


def download(url, filename, reporthook=None):
    with closing(urlopen(url)) as fp:
        headers = fp.info()
        with open(filename, 'wb') as tfp:
            bs = 1024 * 8
            size = -1
            read = 0
            blocknum = 0
            if "content-length" in headers:
                size = int(headers["Content-Length"])

            if reporthook:
                reporthook(blocknum, bs, size)

            while True:
                block = fp.read(bs)
                if not block:
                    break
                read += len(block)
                tfp.write(block)
                blocknum += 1
                if reporthook:
                    reporthook(blocknum, bs, size)


def report_hook(blocks_read, block_size, total_byte):
    global start_time
    if blocks_read == 0:
        start_time = time.time()
        return
    duration = time.time() - start_time
    progress_size = int(blocks_read * block_size)
    speed = progress_size / (1024 * 1024 * duration) if duration > 0 else 0
    percent = min(int(blocks_read * block_size * 100 / total_byte), 100)
    time_remaining = (total_byte - progress_size) / (1024 * 1024 * speed) if speed > 0 else 0
    time_remaining = time_remaining if time_remaining > 0 else 0
    progress_bar = '=' * int(percent / 5) + ('>' if percent < 100 else '')
    progress_str = '{:>4}% [{:20}] {:,.2f} MB    {:,.2f} MB/s    ETA {:.0f} seconds'.format(
        percent, progress_bar, progress_size / (1024 * 1024), speed, time_remaining)
    sys.stdout.write('{:80}\r'.format(progress_str))
    sys.stdout.flush()


def main():
    # Check minimal Python version is 2.7
    if sys.version_info < (2, 7):
        sys.stderr.write('You need Python 2.7 or later\n')
        sys.exit(1)

    # Setup url and file paths
    url = 'http://softwareupdate.vmware.com/cds/vmw-desktop/fusion/'
    dest = os.path.dirname(os.path.abspath(__file__))

    # Re-create the tools folder
    shutil.rmtree(dest + '/tools', True)
    os.mkdir(dest + '/tools')

    # Get the list of Fusion releases
    # And get the last item in the ul/li tags
    response = urlopen(url)
    html = response.read()
    parser = CDSParser()
    parser.feed(str(html))
    url = url + parser.HTMLDATA[-1] + '/'
    parser.clean()

    # Open the latest release page
    # And build file URL
    response = urlopen(url)
    html = response.read()
    parser.feed(str(html))
    last_version = parser.HTMLDATA[-1]
    parser.clean()
    urlpost15 = url + last_version + '/packages/com.vmware.fusion.tools.darwin.zip.tar'
    urlpre15 = url + last_version + '/packages/com.vmware.fusion.tools.darwinPre15.zip.tar'

    # Download the darwin.iso tgz file
    print('Retrieving Darwin tools from: ' + urlpost15)
    try:
        # Try to get tools from packages folder
        download(urlpost15, convertpath(dest + '/tools/com.vmware.fusion.tools.darwin.zip.tar'), report_hook)
    except:
        url_fusion_app = url + last_version + '/core/com.vmware.fusion.zip.tar'

        # Get the fusion app file
        print('Tools aren\'t found. Please wait while downloading from another source.')
        try:
            print('Retrieving Fusion App from: ' + url_fusion_app)
            download(url_fusion_app, convertpath(dest + '/tools/com.vmware.fusion.zip.tar'), report_hook)
        except:
            print('Couldn\'t find tools')
            return

        print()
        tar = tarfile.open(convertpath(dest + '/tools/com.vmware.fusion.zip.tar'), 'r')
        tar.extract('com.vmware.fusion.zip', path=convertpath(dest + '/tools/'))
        tar.close()

        # Extract the iso files from zip
        cdszip = zipfile.ZipFile(convertpath(dest + '/tools/com.vmware.fusion.zip'), 'r')
        cdszip.extract('payload/VMware Fusion.app/Contents/Library/isoimages/darwin.iso',
                       path=convertpath(dest + '/tools/'))
        cdszip.extract('payload/VMware Fusion.app/Contents/Library/isoimages/darwinPre15.iso',
                       path=convertpath(dest + '/tools/'))
        cdszip.close()

        # Move the iso and sig files to tools folder
        shutil.move(convertpath(dest + '/tools/payload/VMware Fusion.app/Contents/Library/isoimages/darwin.iso'),
                    convertpath(dest + '/tools/darwin.iso'))
        shutil.move(convertpath(dest + '/tools/payload/VMware Fusion.app/Contents/Library/isoimages/darwinPre15.iso'),
                    convertpath(dest + '/tools/darwinPre15.iso'))

        # Cleanup working files and folders
        shutil.rmtree(convertpath(dest + '/tools/payload'), True)
        os.remove(convertpath(dest + '/tools/com.vmware.fusion.zip.tar'))
        os.remove(convertpath(dest + '/tools/com.vmware.fusion.zip'))
        return

    # Extract the tar to zip
    tar = tarfile.open(convertpath(dest + '/tools/com.vmware.fusion.tools.darwin.zip.tar'), 'r')
    tar.extract('com.vmware.fusion.tools.darwin.zip', path=convertpath(dest + '/tools/'))
    tar.close()

    # Extract the iso and sig files from zip
    cdszip = zipfile.ZipFile(convertpath(dest + '/tools/com.vmware.fusion.tools.darwin.zip'), 'r')
    cdszip.extract('payload/darwin.iso', path=convertpath(dest + '/tools/'))
    cdszip.extract('payload/darwin.iso.sig', path=convertpath(dest + '/tools/'))
    cdszip.close()

    # Move the iso and sig files to tools folder
    shutil.move(convertpath(dest + '/tools/payload/darwin.iso'), convertpath(dest + '/tools/darwin.iso'))
    shutil.move(convertpath(dest + '/tools/payload/darwin.iso.sig'), convertpath(dest + '/tools/darwin.iso.sig'))

    # Cleanup working files and folders
    shutil.rmtree(convertpath(dest + '/tools/payload'), True)
    os.remove(convertpath(dest + '/tools/com.vmware.fusion.tools.darwin.zip.tar'))
    os.remove(convertpath(dest + '/tools/com.vmware.fusion.tools.darwin.zip'))

    # Download the darwinPre15.iso tgz file
    print('Retrieving DarwinPre15 tools from: ' + urlpre15)
    urlretrieve(urlpre15, convertpath(dest + '/tools/com.vmware.fusion.tools.darwinPre15.zip.tar'))

    # Extract the tar to zip
    tar = tarfile.open(convertpath(dest + '/tools/com.vmware.fusion.tools.darwinPre15.zip.tar'), 'r')
    tar.extract('com.vmware.fusion.tools.darwinPre15.zip', path=convertpath(dest + '/tools/'))
    tar.close()

    # Extract the iso and sig files from zip
    cdszip = zipfile.ZipFile(convertpath(dest + '/tools/com.vmware.fusion.tools.darwinPre15.zip'), 'r')
    cdszip.extract('payload/darwinPre15.iso', path=convertpath(dest + '/tools/'))
    cdszip.extract('payload/darwinPre15.iso.sig', path=convertpath(dest + '/tools/'))
    cdszip.close()

    # Move the iso and sig files to tools folder
    shutil.move(convertpath(dest + '/tools/payload/darwinPre15.iso'),
                convertpath(dest + '/tools/darwinPre15.iso'))
    shutil.move(convertpath(dest + '/tools/payload/darwinPre15.iso.sig'),
                convertpath(dest + '/tools/darwinPre15.iso.sig'))

    # Cleanup working files and folders
    shutil.rmtree(convertpath(dest + '/tools/payload'), True)
    os.remove(convertpath(dest + '/tools/com.vmware.fusion.tools.darwinPre15.zip.tar'))
    os.remove(convertpath(dest + '/tools/com.vmware.fusion.tools.darwinPre15.zip'))


if __name__ == '__main__':
    main()
