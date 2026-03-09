"""
Code for showing filters, reflectances and their products.
"""
import numpy as np
from PySide2 import QtWidgets
from poetry.console.commands import self

from pcot.cameras.filters import Filter
from pcot.ui import uiloader
from pcot import cameras


class Dialog(QtWidgets.QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        uiloader.loadUi('showcamsrefls.ui', self)
        self.cameraBox.currentIndexChanged.connect(self._camera_or_target_changed)
        self.reflBox.currentIndexChanged.connect(self._camera_or_target_changed)
        self.filterPlotButton.clicked.connect(self._filter_plot)
        self.filterAngleSpin.valueChanged.connect(self._filter_plot)
        self.y01Box.stateChanged.connect(self._camera_or_target_changed)
        self.reflPlotButton.clicked.connect(self._refl_plot)
        self.filtReflPlotButton.clicked.connect(self._filt_refl_plot)

        # populate the boxes for the cameras
        for cname in cameras.getCameraNames():
            self.cameraBox.addItem(cname)
        # and the reflectances
        for rname in cameras.getReflectanceNames():
            self.reflBox.addItem(rname)
        self._camera_or_target_changed()

    def _camera_or_target_changed(self):
        # get currently selected items
        curPatch = self.patchBox.currentText()
        curFilter = self.filterBox.currentText()

        # add new items, starting by clearing and adding ALL
        self.patchBox.clear()
        self.filterBox.clear()
        self.patchBox.addItem("ALL")
        self.filterBox.addItem("ALL")
        # add the currently selected camera's filters
        cam = cameras.getCamera(self.cameraBox.currentText())
        for filter in cam.params.filters:
            self.filterBox.addItem(filter)
        # add patches for the currently selected target
        rname = self.reflBox.currentText()
        if rname is not None and rname!="":
            refl = cameras.getReflectance(rname)
            for p in refl.get_patches():
                self.patchBox.addItem(p)

        # and try to set the previously selected items, which may fail (which is OK)
        self.patchBox.setCurrentText(curPatch)
        self.filterBox.setCurrentText(curFilter)

    def _init_plot(self, ylab):
        mpl = self.mpl_widget
        mpl.clear()
        ax = mpl.ax
        ax.cla()
        ax.set_xlabel("Wavelength (nm)")
        ax.set_ylabel(ylab)
        return mpl, ax

    def _filter_plot(self):
        self.errorText.setText("")
        cam = cameras.getCamera(self.cameraBox.currentText())
        filter_names = cam.params.filters
        selected = self.filterBox.currentText()
        mpl, ax = self._init_plot("response")

        not_filter = []
        wavelengths = np.linspace(300, 1200, 400)
        angle = self.filterAngleSpin.value()
        for n in filter_names:
            f = cam.getFilter(n)
            if not isinstance(f, Filter):
                not_filter.append(n)
                continue
            if n == selected or selected == "ALL":
                # get the response for a range of wavelengths
                resp = f.getResponse(wavelengths, angle)
                label = f.name
                if f.response.is_simulated:
                    label += " (sim)"
                if f.response.clipped_to:
                    label += f" (clipped to {f.response.clipped_to}%)"
                ax.plot(wavelengths, resp, label=label )
                if f.response.clipped_to:
                    # find the part of the response that is equal to the clipped level
                    xs = np.where(np.abs(resp-f.response.clipped_to/100) < 0.000001)[0]
                    if len(xs)>0:
                        ax.hlines(f.response.clipped_to/100, wavelengths[xs[0]], wavelengths[xs[-1]],
                                  linewidth=3, color="r")

        if len(not_filter) > 0:
            self.errorText.setText(f"Not true filters: {', '.join(not_filter)}")
        ax.legend()
        if self.y01Box.isChecked():
            ax.set_ylim([0, 1])
        mpl.draw()

    def _refl_plot(self):
        self.errorText.setText("")
        phi = self.phiSpin.value()
        theta = self.thetaSpin.value()
        refl = cameras.getReflectance(self.reflBox.currentText())
        selected = self.patchBox.currentText()

        mpl, ax = self._init_plot("reflectance")

        for n in refl.get_patches():
            if n==selected or selected == "ALL":
                wavelengths, r = refl.get_reflectances(n, phi, theta)
                ax.plot(wavelengths, r, label=n)

        ax.legend()
        mpl.draw()

    def _filt_refl_plot(self):
        """Here we multiply the filter response by the reflectance"""
        phi = self.phiSpin.value()
        theta = self.thetaSpin.value()
        filt_angle = self.filterAngleSpin.value()
        refl = cameras.getReflectance(self.reflBox.currentText())
        selected_patch = self.patchBox.currentText()
        cam = cameras.getCamera(self.cameraBox.currentText())
        selected_filter = self.filterBox.currentText()
        self.errorText.setText("")

        # You have to pick one of each, otherwise clutter.
        if selected_filter == "ALL":
            self.errorText.setText("Must select a filter")
            return
        if selected_patch == "ALL":
            self.errorText.setText("Must select a patch")
            return

        filter = cam.getFilter(selected_filter)
        if not isinstance(filter, Filter): # it has to be a real filter
            self.errorText.setText(f"Not a true filter: {selected_filter}")
            return

        # get the reflectances for the patch
        wavelengths, refls = refl.get_reflectances(selected_patch, phi, theta)

        # get the filter responses at those wavelengths
        resp = filter.getResponse(wavelengths,filt_angle)

        # multiply the two together at each wavelength
        res = refls * resp
        # and get the "known reflectance" total
        known = refl.get_known_reflectance_for_filter(filter, selected_patch, phi, theta, filt_angle)

        mpl, ax = self._init_plot("filtered refl.")

        # plot all three things
        ax.plot(wavelengths, refls, label=selected_patch)
        ax.plot(wavelengths, resp, label=selected_filter)
        ax.plot(wavelengths, res, label=f"{selected_patch} * {selected_filter}")
        ax.fill_between(wavelengths, res, alpha=0.5)
        ax.hlines([known], wavelengths[0], wavelengths[-1], colors="r")
        ax.annotate(f"{known:.4}", (wavelengths[-1], known), fontsize=8, ha='right')
        ax.legend()
        mpl.draw()
        ax.legend()
        mpl.draw()

        ax.legend()
        mpl.draw()



