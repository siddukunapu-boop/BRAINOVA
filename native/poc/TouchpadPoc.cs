using System;
using System.Drawing;
using System.Runtime.InteropServices.WindowsRuntime;
using System.Windows.Forms;
using Windows.Foundation;
using Windows.UI.Core;
using Windows.UI.Input;

namespace BrainovaTouchpadPoc
{
    public class PocForm : Form
    {
        private readonly TextBox _log;
        private readonly Label _statusLabel;
        private TouchpadGesturesController _controller;

        public PocForm()
        {
            Text = "BRAINOVA TouchpadGesturesController PoC";
            Width = 760;
            Height = 520;
            BackColor = Color.FromArgb(11, 16, 32);
            ForeColor = Color.White;

            _statusLabel = new Label
            {
                Dock = DockStyle.Top,
                Height = 56,
                Padding = new Padding(12),
                Font = new Font("Segoe UI", 11, FontStyle.Bold),
                Text = "Initializing TouchpadGesturesController..."
            };

            var toggleBtn = new Button
            {
                Dock = DockStyle.Top,
                Height = 38,
                Text = "Toggle Controller Enabled",
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(30, 42, 82),
                ForeColor = Color.White
            };
            toggleBtn.Click += (s, e) => ToggleController();

            _log = new TextBox
            {
                Dock = DockStyle.Fill,
                Multiline = true,
                ReadOnly = true,
                ScrollBars = ScrollBars.Vertical,
                BackColor = Color.FromArgb(16, 23, 45),
                ForeColor = Color.FromArgb(203, 213, 225),
                Font = new Font("Consolas", 10)
            };

            Controls.Add(_log);
            Controls.Add(toggleBtn);
            Controls.Add(_statusLabel);

            Load += (s, e) => InitTouchpadController();
            FormClosing += (s, e) => ReleaseController();
        }

        private void AppendLog(string msg)
        {
            if (InvokeRequired)
            {
                BeginInvoke((Action)(() => AppendLog(msg)));
                return;
            }
            _log.AppendText("[" + DateTime.Now.ToString("HH:mm:ss.fff") + "] " + msg + Environment.NewLine);
        }

        private void InitTouchpadController()
        {
            try
            {
                bool supported = TouchpadGesturesController.IsSupported();
                AppendLog("TouchpadGesturesController.IsSupported() = " + supported);
                if (!supported)
                {
                    _statusLabel.Text = "TouchpadGesturesController is NOT supported on this device.";
                    return;
                }

                _controller = TouchpadGesturesController.CreateForProcess();
                if (_controller == null)
                {
                    _statusLabel.Text = "CreateForProcess() returned null.";
                    AppendLog("CreateForProcess() returned null.");
                    return;
                }

                _controller.SupportedGestures =
                    TouchpadGlobalGestureKinds.ThreeFingerManipulations |
                    TouchpadGlobalGestureKinds.FourFingerManipulations |
                    TouchpadGlobalGestureKinds.ThreeFingerActions |
                    TouchpadGlobalGestureKinds.FourFingerActions;

                _controller.PointerPressed += (TouchpadGesturesController sender, PointerEventArgs args) =>
                {
                    args.Handled = true;
                    AppendLog("PointerPressed (Handled=true) PointerId=" + args.CurrentPoint.PointerId);
                };
                _controller.PointerMoved += (TouchpadGesturesController sender, PointerEventArgs args) =>
                {
                    args.Handled = true;
                    AppendLog("PointerMoved (Handled=true) PointerId=" + args.CurrentPoint.PointerId);
                };
                _controller.PointerReleased += (TouchpadGesturesController sender, PointerEventArgs args) =>
                {
                    args.Handled = true;
                    AppendLog("PointerReleased (Handled=true) PointerId=" + args.CurrentPoint.PointerId);
                };
                _controller.GlobalActionPerformed += (TouchpadGesturesController sender, TouchpadGlobalActionEventArgs args) =>
                {
                    AppendLog("GlobalActionPerformed: " + args.ToString());
                };

                _controller.Enabled = true;
                _statusLabel.Text = "Controller ACTIVE | Enabled=" + _controller.Enabled + " | Gestures=" + _controller.SupportedGestures;
                AppendLog("Controller Enabled=true, SupportedGestures=" + _controller.SupportedGestures);
                AppendLog("Try swiping 3 fingers upward on the touchpad while this window is focused.");
            }
            catch (Exception ex)
            {
                _statusLabel.Text = "Error: " + ex.Message;
                AppendLog("Exception: " + ex);
            }
        }

        private void ToggleController()
        {
            if (_controller == null) return;
            _controller.Enabled = !_controller.Enabled;
            _statusLabel.Text = "Controller Enabled=" + _controller.Enabled + " | Gestures=" + _controller.SupportedGestures;
            AppendLog("Toggled Controller Enabled=" + _controller.Enabled);
        }

        private void ReleaseController()
        {
            if (_controller != null)
            {
                try
                {
                    _controller.Enabled = false;
                    AppendLog("Controller disabled on exit.");
                }
                catch { }
            }
        }

        [STAThread]
        public static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new PocForm());
        }
    }
}
