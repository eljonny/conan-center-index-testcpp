from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.apple import fix_apple_shared_install_name
from conan.tools.meson import Meson, MesonToolchain
from conan.tools.gnu import PkgConfigDeps
from conan.tools.scm import Version
from conan.tools.env import VirtualBuildEnv
from conan.tools.microsoft import is_msvc
from conan.tools.files import apply_conandata_patches, copy, export_conandata_patches, rmdir, rename, get, rm, replace_in_file
from conan.tools.build import cross_building, check_min_cppstd
from conan.tools.layout import basic_layout
import shutil
import os


required_conan_version = ">=1.53.0"


class LibXMLPlusPlus(ConanFile):
    name = "libxmlpp"
    description = "libxml++ (a.k.a. libxmlplusplus) provides a C++ interface to XML files"
    license = "LGPL-2.1"
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://github.com/libxmlplusplus/libxmlplusplus"
    topics = ("xml", "parser", "wrapper")
    package_type = "library"
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
    }

    @property
    def _min_cppstd(self):
        return "17" if Version(self.version) >= "5.4.0" else "11"

    @property
    def _compilers_minimum_version(self):
        return {
            "17": {
                "gcc": "8",
                "clang": "7",
                "apple-clang": "12",
                "Visual Studio": "16",
                "msvc": "192",
            },
        }.get(self._min_cppstd, {})

    @property
    def _lib_version(self):
        return "5.0"

    def export_sources(self):
        export_conandata_patches(self)

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def configure(self):
        if self.options.shared:
            self.options.rm_safe("fPIC")

    def layout(self):
        basic_layout(self, src_folder="src")

    def requirements(self):
        self.requires("libxml2/[>=2.12.5 <3]")
        self.requires("glibmm/2.75.0")

    def validate(self):
        if hasattr(self, "settings_build") and cross_building(self):
            raise ConanInvalidConfiguration("Cross-building not implemented")
        if self.settings.compiler.get_safe("cppstd"):
            check_min_cppstd(self, self._min_cppstd)
        minimum_version = self._compilers_minimum_version.get(str(self.settings.compiler), False)
        if minimum_version and Version(self.settings.compiler.version) < minimum_version:
            raise ConanInvalidConfiguration(
                f"{self.ref} requires C++{self._min_cppstd}, which your compiler does not support."
            )

    def build_requirements(self):
        self.tool_requires("meson/[>=1.2.3 <2]")
        if not self.conf.get("tools.gnu:pkg_config", check_type=str):
            self.tool_requires("pkgconf/[>=2.2 <3]")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def _patch_sources(self):
        apply_conandata_patches(self)

        if is_msvc(self):
            # when using cpp_std=c++NM the /permissive- flag is added which
            # attempts enforcing standard conformant c++ code. the problem is
            # that older versions of the Windows SDK isn't standard conformant!
            # see:
            # https://developercommunity.visualstudio.com/t/error-c2760-in-combaseapih-with-windows-sdk-81-and/185399
            replace_in_file(self,
                os.path.join(self.source_folder, "meson.build"),
                "cpp_std=c++", "cpp_std=vc++")

    def generate(self):
        virtual_build_env = VirtualBuildEnv(self)
        virtual_build_env.generate()
        tc = MesonToolchain(self)
        tc.project_options["build-examples"] = "false"
        tc.project_options["build-tests"] = "false"
        tc.project_options["build-documentation"] = "false"
        tc.project_options["msvc14x-parallel-installable"] = "false"
        tc.project_options["default_library"] = "shared" if self.options.shared else "static"
        tc.generate()
        td = PkgConfigDeps(self)
        td.generate()

    def build(self):
        self._patch_sources()
        meson = Meson(self)
        meson.configure()
        meson.build()

    def package(self):
        copy(self, "COPYING", dst=os.path.join(self.package_folder, "licenses"), src=self.source_folder)
        meson = Meson(self)
        meson.install()

        shutil.move(
            os.path.join(self.package_folder, "lib", f"libxml++-{self._lib_version}", "include", "libxml++config.h"),
            os.path.join(self.package_folder, "include", f"libxml++-{self._lib_version}", "libxml++config.h"))

        rmdir(self, os.path.join(self.package_folder, "lib", "pkgconfig"))
        rmdir(self, os.path.join(self.package_folder, "lib", f"libxml++-{self._lib_version}"))
        fix_apple_shared_install_name(self)

        if is_msvc(self):
            rm(self, "*.pdb", os.path.join(self.package_folder, "bin"))
            if not self.options.shared:
                rename(
                    self,
                    os.path.join(self.package_folder, "lib", f"libxml++-{self._lib_version}.a"),
                    os.path.join(self.package_folder, "lib", f"xml++-{self._lib_version}.lib"))

    def package_info(self):
        self.cpp_info.set_property("pkg_config_name", f"libxml++-{self._lib_version}")
        self.cpp_info.libs = [f"xml++-{self._lib_version}"]
        self.cpp_info.includedirs = [os.path.join("include", f"libxml++-{self._lib_version}")]
