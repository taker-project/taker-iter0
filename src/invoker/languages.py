from os import path
import shutil
from .config import config
from compat import fspath


class Language:
    def _lang_section_name(self):
        return 'lang/' + self.name

    def _lang_section(self):
        return config()[self._lang_section_name()]

    def _compile_args_template(self):
        return self._lang_section().get('compile-args')

    def _run_args_template(self):
        return self._lang_section().get('run-args')

    def get_extensions(self):
        return [self.name.partition('.')[0]]

    def _finalize_arglist(self, args):
        # get full path of the executable
        first_arg = shutil.which(args[0])
        if first_arg is None:
            raise FileNotFoundError('cannot find executable "{}"'
                                    .format(args[0]))
        args[0] = first_arg

    def compile_args(self, src_file, exe_file, library_dirs=[]):
        src_file = src_file.absolute()
        exe_file = exe_file.absolute()
        args_template = self._compile_args_template()
        if not args_template:
            return None
        res = []
        # FIXME : support {curly braces} inside the templates
        mapping = {
            'src': fspath(src_file),
            'exe': fspath(exe_file),
        }
        for arg in args_template:
            if arg.find('{lib}') >= 0:
                for lib in library_dirs:
                    mapping['lib'] = fspath(lib.absolute())
                    res += [arg.format_map(mapping)]
                continue
            res += [arg.format_map(mapping)]
        self._finalize_arglist(res)
        return res

    def run_args(self, exe_file, custom_args=[]):
        exe_file = exe_file.absolute()
        args_template = self._run_args_template()
        if not args_template:
            args_template = ['{exe}']
        mapping = {'exe': fspath(exe_file.resolve())}
        res = [arg.format_map(mapping) for arg in args_template]
        self._finalize_arglist(res)
        return res + custom_args

    def __lt__(self, other):
        return self.priority > other.priority

    def __init__(self, name, priority=0):
        self.name = name
        self.priority = self._lang_section().get('priority')
        if self.priority is None:
            self.priority = priority


class PredefinedLanguage(Language):
    def _compile_args_template(self):
        res = super()._compile_args_template()
        if res is not None:
            return res
        return self.__compile_args_template

    def _run_args_template(self):
        res = super()._run_args_template()
        if res is not None:
            return res
        return self.__run_args_template

    def __init__(self, name, priority=None, compile_args=None, run_args=None):
        super().__init__(name, priority)
        self.__compile_args_template = compile_args
        self.__run_args_template = run_args


class LanguageManagerBase:
    def try_add_language(self, language):
        if language.name in self:
            return False
        self.add_language(language)
        return True

    def add_language(self, language):
        name = language.name
        extensions = language.get_extensions()
        assert name not in self._languages
        self._languages[name] = language
        for ext in extensions:
            self._extensions.setdefault(ext, [])
            self._extensions[ext] += [language]

    def get_lang(self, name):
        return self._languages[name]

    def get_ext(self, ext):
        return sorted(self._extensions.get(ext, []))

    def __getitem__(self, name):
        return self.get_lang(name)

    def __contains__(self, name):
        return name in self._languages

    def _predefine(self):
        self.add_language(PredefinedLanguage(
            'c.gcc',
            priority=1000,
            compile_args=['gcc', '{src}', '-o', '{exe}', '-O2', '-I{lib}']
        ))
        self.add_language(PredefinedLanguage(
            'cpp.g++',
            priority=1000,
            compile_args=['g++', '{src}', '-o', '{exe}', '-O2', '-I{lib}']
        ))
        self.add_language(PredefinedLanguage(
            'cpp.g++11',
            priority=1100,
            compile_args=['g++', '{src}', '-o', '{exe}', '-O2', '--std=c++11',
                          '-I{lib}']
        ))
        self.add_language(PredefinedLanguage(
            'cpp.g++14',
            priority=1200,
            compile_args=['g++', '{src}', '-o', '{exe}', '-O2', '--std=c++14',
                          '-I{lib}']
        ))
        self.add_language(PredefinedLanguage(
            'pas.fpc',
            priority=1000,
            compile_args=['fpc', '{src}', '-o{exe}', '-Fi{lib}', '-FU{lib}']
        ))
        self.add_language(PredefinedLanguage(
            'py.py2',
            priority=1000,
            run_args=['python2', '{exe}']
        ))
        self.add_language(PredefinedLanguage(
            'py.py3',
            priority=1100,
            run_args=['python3', '{exe}']
        ))
        # TODO : add more languages!

    def reload(self):
        self._languages.clear()
        self._extensions.clear()
        self._predefine()
        for section in config():
            if section[0].startswith('lang/'):
                name = section[0].partition('/')[2]
                self.try_add_language(Language(name))

    def __init__(self):
        self._languages = {}
        self._extensions = {}
        self.reload()
