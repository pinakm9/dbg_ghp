import re

UNIDENTIFIED = -1
ATTR         =  0
ADT          =  1
END          =  2

REGEX = { ATTR    : '^\s*([*\w]*)\s+([*\w\[\]]*)\s*([*\w\[\]]*)?\s*;\s*$',
          ADT     : '^\s*([^{\s]*)\s*([^{\s]*)\s*([^{\s]*)\s*{\s*$',
          END     : '^\s*}([^;]*);\s*$', }

class ParseLine:

    def __init__(self, text, raw = False):
        self.txt = text
        self.state = UNIDENTIFIED
        self.data = []
        for key in range(len(REGEX)):
            matchobj = re.match(REGEX[key], self.txt)
            if matchobj is not None:
                self.state = key
                self.data = matchobj.groups() if raw else self.clean( list( map( lambda x: ''.join(x.split()), matchobj.groups() ) ) )
                break

    def clean(self, l, item = ''):
        return [ e for e in l if e is not item ]

class ParseADT:

    def __init__(self, text):
        lines = text.split('\n')
        data = ParseLine(lines[0]).data
        if 'typedef' in data:
            data.remove('typedef')
        self.type = data[0]
        self.names = []
        if len(data) > 1:
            self.names.append(data[1])
        self.defn = '\n'.join(lines[1:-1])
        self.names += ParseLine(lines[len(lines) - 1]).data[0].replace(',',' ').split()

class Parse:

    CT = {'struct' : 'Structure', 'union' : 'Union'}

    def __init__(self, path_to_file):
        with open(path_to_file, 'r') as text:
            self.lines = text.read().split('\n')
        self.depth = 0
        self.stack = []
        self.adt = None
        self.py = ''
        self.rewrite()

    def find_end(self, k, ls = '{', rs = '}'):
        j, lc, rc = k+1, 0, 0
        while lc >= rc:
            if ls in self.lines[j]:
                lc += 1
            elif rs in self.lines[j]:
                rc +=1
            j += 1
        return j

    def _3_fix(self, l): # handles 3 matches for ATTR
        if len(l) == 3:
            l = l[1:3]
        return l

    def a_fix(self, l): # a-->Array
        parts = re.sub('\[|\]', '\t', l[1]).split('\t')
        if len(parts) > 1:
            l = [ l[0] + ' * ' + parts[1], parts[0] ]
        return l

    def p_fix(self, l): # p-->Pointer
        type_ , var = l[0], l[1].lstrip('*')
        pc = len(l[1]) - len(var)
        type_ = 'ctypes.POINTER(' * pc + type_ + ')' * pc
        return [type_ , var]

    def t_fix(self, l): # t-->Type
        for key in self.CT:
            if l == key:
                l = 'ctypes.' + self.CT[key]
                break
        return l

    def fix(self, l):
        l = self._3_fix(l)
        l = self.p_fix(l)
        l = self.a_fix(l)
        return l

    def push(self, j):
        adt = ParseADT( '\n'.join(self.lines[j : self.find_end(j)]) )
        if self.depth > 0:
            adt.names[0] = self.adt.names[0] + '_' + adt.names[0]
        adt.type = self.t_fix(adt.type)
        self.depth += 1
        self.stack.append(adt)
        self.adt = adt

    def pop(self):
        self.depth -= 1
        self.stack.pop()
        self.adt = self.stack[self.depth - 1] if self.depth > 0 else None

    def bubble_class(self):
        lines, defs, other = self.py.split('\n'), [], []
        lc, j = len(lines), 0
        while j < lc:
            if lines[j].startswith('class'):
                defs += lines[j:j+2]
                j += 2
            else:
                other.append(lines[j])
                j += 1
        self.py = '\n'.join(defs + other)

    def untangle(self,text):
        quanta = ''
        while True:
            matchobj = re.search('(\s[.\w]+\s*=\s*\[\s+[^\[\]]*\])', text)
            if matchobj is not None:
                quantum = matchobj.group(1)
                text = text.replace(quantum, '')
                quanta += quantum
            else:
                text += quanta
                break
        return text
        #print(text)

    def rewrite(self):
        for line_no, line in enumerate(self.lines):
            line = ParseLine(line)
            if line.state == ATTR:
                self.py += '\t("{2}",\t{1}),\n'.format(self.adt.names[0], *self.fix(line.data))
            elif line.state == ADT:
                self.push(line_no)
                self.py += 'class {0}({1}):\n\tpass\n{0}._fields_ = [\n'.format(self.adt.names[0], self.adt.type)
            elif line.state == END:
                self.py += '\t]\n'
                if self.depth > 1:
                    name = self.adt.names[0]
                    self.pop()
                    main = self.adt.names[0]
                    self.py += '\t("{1}",\t{2}),\n'.format(main, name.replace(main + '_', ''), name)
                elif self.depth == 1:
                    for i in range(1, len(self.adt.names)):
                        self.py += '{1} = {0}\n'.format(*self.p_fix([self.adt.names[0], self.adt.names[i]]))
        self.bubble_class()
        self.py = self.untangle(self.py)

print(Parse('struct.txt').py)
