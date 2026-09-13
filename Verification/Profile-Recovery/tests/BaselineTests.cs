using System;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Windows.Forms;
internal static class BaselineTests
{
    static string Make(string root)
    {
        foreach(string item in MSRLauncher.Required) { string file=Path.Combine(root,MSRLauncher.Versions[0],"game",item);Directory.CreateDirectory(Path.GetDirectoryName(file));File.WriteAllText(file,"inert; never execute"); }
        MSRLauncher.Prepare(root,MSRLauncher.Versions[0],"127.0.0.1:27025",true);
        return File.ReadAllText(Path.Combine(root,MSRLauncher.Versions[0],"player-profile.json"));
    }
    [STAThread] static int Main()
    {
        try
        {
            Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
            string work=Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"fixtures","baseline-"+Guid.NewGuid().ToString("N"));
            string old=Make(Path.Combine(work,"Old installation"));string fresh=Make(Path.Combine(work,"Reinstalled folder"));
            if(old==fresh)throw new Exception("Expected baseline to create different new identity.");
            Console.WriteLine("PASS: unchanged baseline reproduces new identity after reinstall; no durable recovery.");
            using(LauncherForm form=new LauncherForm(Path.Combine(work,"Old installation"),MSRLauncher.Versions[0]))using(Bitmap image=new Bitmap(form.Width,form.Height)){form.StartPosition=FormStartPosition.Manual;form.Location=new Point(-32000,-32000);form.ShowInTaskbar=false;form.Show();Application.DoEvents();foreach(Control control in form.Controls){IntPtr handle=control.Handle;}form.PerformLayout();Application.DoEvents();form.DrawToBitmap(image,new Rectangle(0,0,image.Width,image.Height));image.Save(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"old-launcher.png"));}
            File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"baseline-results.json"),"{\"status\":\"PASS\",\"baseline_identity_loss_reproduced\":true,\"game_or_network_started\":false}");return 0;
        }
        catch(Exception error){Console.WriteLine(error);return 1;}
    }
}
